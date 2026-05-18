#!/usr/bin/env python3
"""
Bear Lake Property Due Diligence Scraper  v2.0
===============================================
Property : 14638 Pleasanton Hwy, Bear Lake (Pleasanton Twp), MI 49614
Parcel   : 26101-1202140002

Install (core):
  pip install requests beautifulsoup4 lxml pdfplumber

Install (optional — enables extra checks):
  pip install geopandas shapely fiona          # shapefile wetlands check
  pip install selenium undetected-chromedriver  # JS-heavy site fallback
  pip install openai                            # GPT-4o photo analysis

Run:
  python bear_lake_scraper.py                  # default: all checks, no selenium
  python bear_lake_scraper.py --selenium       # enable Selenium fallback
  python bear_lake_scraper.py --geopandas      # download NWI shapefile (~100 MB)
  python bear_lake_scraper.py --vision gpt-4o  # add photo vision analysis
  python bear_lake_scraper.py --skip deed dhd10 # skip slow/unavailable steps
"""

import argparse
import functools
import json
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────────────────────────────────────
# PROPERTY CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
PROPERTY = {
    "address":  "14638 Pleasanton Hwy, Bear Lake, MI 49614",
    "apn":      "26101-1202140002",
    "bsa_uid":  "2022",       # Manistee County BS&A client ID
    "zpid":     "106451402",  # Zillow property ID
    "mls":      "25057116",
    "lat":      44.4330,      # fallback if geocoder fails
    "lon":      -86.1430,
    "owner":    "David Golden / Delores Golden",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

ZONE_DESCRIPTIONS = {
    "X":    "✔ Minimal flood hazard — outside 500-yr flood plain",
    "X500": "Moderate risk — within 500-yr flood plain",
    "A":    "⚠ HIGH RISK — SFHA, 100-yr flood plain (no BFE)",
    "AE":   "⚠ HIGH RISK — SFHA, 100-yr flood plain with BFE",
    "AH":   "⚠ HIGH RISK — Shallow flooding 1–3 ft",
    "AO":   "⚠ HIGH RISK — Sheet-flow flooding 1–3 ft",
    "VE":   "⚠ HIGH RISK — Coastal with wave action",
    "D":    "Undetermined flood hazard",
}


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _warn(msg: str) -> None:
    print(f"  ⚠  {msg}", file=sys.stderr)


def _section(title: str) -> None:
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


def _print_dict(d: dict, max_items: int = 10) -> None:
    shown = 0
    for k, v in d.items():
        if shown >= max_items:
            print(f"  … ({len(d) - shown} more fields)")
            break
        print(f"  {k}: {str(v)[:120]}")
        shown += 1


def retry(times: int = 3, delay: float = 2.0,
          on: tuple = (requests.RequestException,)):
    """Exponential-backoff retry decorator."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(times):
                try:
                    return fn(*args, **kwargs)
                except on as exc:
                    last_exc = exc
                    if attempt < times - 1:
                        time.sleep(delay * (2 ** attempt))
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────────────────────────
# 1. GEOCODING
# ──────────────────────────────────────────────────────────────────────────────
@retry(times=3, delay=2.0)
def geocode_address(address: str) -> tuple[float | None, float | None]:
    """US Census geocoder — free, no API key."""
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    r = requests.get(url, params={
        "address": address, "benchmark": "Public_AR_Current", "format": "json",
    }, timeout=15, headers=HEADERS)
    r.raise_for_status()
    matches = r.json().get("result", {}).get("addressMatches", [])
    if matches:
        c = matches[0]["coordinates"]
        return float(c["y"]), float(c["x"])
    return None, None


def geocode_nominatim(address: str) -> tuple[float | None, float | None]:
    """OpenStreetMap Nominatim fallback geocoder."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            timeout=15,
            headers={**HEADERS, "User-Agent": "bear-lake-due-diligence/2.0"},
        )
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        _warn(f"Nominatim: {e}")
    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# 2. BS&A ONLINE — TAX RECORDS
# ──────────────────────────────────────────────────────────────────────────────
def get_bsa_tax(apn: str, uid: str = "2022") -> dict:
    """
    Query BS&A Online (Manistee County) for parcel tax data.
    BS&A is ASP.NET/session-heavy. Tries direct POST first.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    base = "https://bsaonline.com"
    result: dict = {}

    try:
        page = session.get(f"{base}/?uid={uid}", timeout=15)
        soup = BeautifulSoup(page.text, "lxml")

        # Harvest CSRF token
        token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
        token = token_tag["value"] if token_tag else ""

        time.sleep(1.2)

        payload = {
            "__RequestVerificationToken": token,
            "SearchType":                 "Parcel",
            "ParcelNumber":               apn,
            "uid":                        uid,
        }
        resp = session.post(
            f"{base}/SiteSearch/TaxRecordSearch?uid={uid}",
            data=payload, timeout=20,
        )
        soup2 = BeautifulSoup(resp.text, "lxml")

        # Try table rows
        for row in soup2.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key and val and len(key) < 60:
                    result[key] = val

        # Try label/value CSS classes
        if not result:
            for tag in soup2.find_all(class_=lambda c: c and "value" in str(c).lower()):
                label_tag = tag.find_previous(
                    class_=lambda c: c and "label" in str(c).lower()
                )
                if label_tag:
                    result[label_tag.get_text(strip=True)] = tag.get_text(strip=True)

        # Extract dollar amounts even from unstructured text
        if not result:
            text = soup2.get_text(" ")
            for pattern, key in [
                (r'Total(?:\s+Summer)?\s+Tax[^\d]*(\$?[\d,]+\.\d{2})', "Total Tax"),
                (r'Winter\s+Tax[^\d]*(\$?[\d,]+\.\d{2})',               "Winter Tax"),
                (r'Summer\s+Tax[^\d]*(\$?[\d,]+\.\d{2})',               "Summer Tax"),
                (r'Taxable\s+Value[^\d]*(\$?[\d,]+)',                   "Taxable Value"),
                (r'S\.?E\.?V\.?[^\d]*(\$?[\d,]+)',                      "SEV"),
                (r'Assessed\s+Value[^\d]*(\$?[\d,]+)',                  "Assessed Value"),
            ]:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    result[key] = m.group(1)

        if result:
            result["_source"] = "BS&A Online (requests)"
        else:
            result["_status"]     = "BLOCKED_OR_NO_RESULTS"
            result["_manual_url"] = f"https://bsaonline.com/?uid={uid}"
            result["_tip"]        = (
                f"Open the URL above and search parcel {apn}. "
                "Run with --selenium flag for automated JS rendering."
            )

    except Exception as e:
        result["_error"]  = str(e)
        result["_status"] = "CONNECTION_ERROR"

    return result


def get_bsa_tax_selenium(apn: str, uid: str = "2022") -> dict:
    """Selenium fallback for BS&A. Requires pip install selenium undetected-chromedriver."""
    try:
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        opts = uc.ChromeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        driver = uc.Chrome(options=opts)

        driver.get(f"https://bsaonline.com/?uid={uid}")
        wait = WebDriverWait(driver, 12)

        for sel in ["input[name*='arcel']", "#parcelNumber",
                    "input[placeholder*='arcel']", "input[id*='arcel']"]:
            try:
                inp = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                inp.clear()
                inp.send_keys(apn)
                driver.find_element(
                    By.CSS_SELECTOR, "button[type='submit'],input[type='submit']"
                ).click()
                time.sleep(3)
                break
            except Exception:
                continue

        soup = BeautifulSoup(driver.page_source, "lxml")
        driver.quit()

        result: dict = {}
        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                k = cells[0].get_text(strip=True)
                v = cells[1].get_text(strip=True)
                if k and v and len(k) < 80:
                    result[k] = v
        result["_source"] = "BS&A Online (Selenium)"
        return result

    except ImportError:
        return {"_error": "pip install selenium undetected-chromedriver"}
    except Exception as e:
        return {"_error": f"Selenium failed: {e}"}


# ──────────────────────────────────────────────────────────────────────────────
# 3. MANISTEE COUNTY LIAA PARCEL VIEWER
# ──────────────────────────────────────────────────────────────────────────────
def get_liaa_parcel(apn: str) -> dict:
    result: dict = {}
    session = requests.Session()
    session.headers.update(HEADERS)
    url = "https://maps.liaa.org/manisteeparcels/propertysearch.asp"

    try:
        session.get(url, timeout=15)
        time.sleep(1)
        resp = session.post(
            url,
            data={"parcel": apn, "submit": "Search", "searchtype": "parcel"},
            timeout=20,
        )
        soup = BeautifulSoup(resp.text, "lxml")

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                k = cells[0].get_text(strip=True).rstrip(":")
                v = cells[1].get_text(strip=True)
                if k and v and k != v and len(k) < 80:
                    result[k] = v

        for dt in soup.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                result[dt.get_text(strip=True)] = dd.get_text(strip=True)

        if result:
            result["_source"] = "Manistee County LIAA"
        else:
            result["_status"]     = "NO_RESULTS"
            result["_manual_url"] = url
            result["_tip"]        = f"Open {url} and search parcel {apn}"

    except Exception as e:
        result["_error"] = str(e)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 4. MICHIGAN STATEWIDE PARCEL API + MANISTEE ARCGIS
# ──────────────────────────────────────────────────────────────────────────────
def get_mi_parcel_api(apn: str, address: str) -> dict:
    """
    Try Michigan GeoAPI (state-level parcel REST) then Manistee County ArcGIS.
    Returns parcel geometry, owner, acreage if accessible.
    """
    result: dict = {}

    # Michigan GeoAPI
    for endpoint in [
        f"https://geoapi.michigan.gov/v1/parcels/?number={apn}&format=json",
        f"https://geoapi.michigan.gov/v1/parcels/?address={requests.utils.quote(address)}&format=json",
    ]:
        try:
            r = requests.get(endpoint, timeout=15, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                features = (data or {}).get("features", [])
                if features:
                    result.update(features[0].get("properties", {}))
                    result["_source"] = "Michigan GeoAPI"
                    return result
        except Exception:
            continue

    # Manistee County ArcGIS REST (standard ESRI endpoint)
    try:
        r = requests.get(
            "https://gis.manisteecountymi.gov/arcgis/rest/services/Parcels/MapServer/0/query",
            params={
                "where":          f"ParcelNumber='{apn}'",
                "outFields":      "*",
                "returnGeometry": "true",
                "f":              "json",
            },
            timeout=15, headers=HEADERS,
        )
        if r.status_code == 200:
            features = r.json().get("features", [])
            if features:
                result.update(features[0].get("attributes", {}))
                result["geometry"] = features[0].get("geometry", {})
                result["_source"]  = "Manistee County ArcGIS"
                return result
    except Exception:
        pass

    result["_status"] = "NOT_FOUND"
    result["_manual"] = "manisteecountymi.gov/333  (county GIS portal)"
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 5. WETLANDS — REST API
# ──────────────────────────────────────────────────────────────────────────────
def check_wetlands(lat: float, lon: float, buffer_m: int = 100) -> dict:
    """USFWS NWI MapServer spatial query, Michigan EGLE fallback."""
    result: dict = {"found": None, "features": [], "source": None}

    spatial_params = {
        "geometry":       f"{lon},{lat}",
        "geometryType":   "esriGeometryPoint",
        "spatialRel":     "esriSpatialRelIntersects",
        "distance":       buffer_m,
        "units":          "esriSRUnit_Meter",
        "inSR":           "4326",
        "outFields":      "WETLAND_TYPE,ATTRIBUTE,ACRES",
        "returnGeometry": "false",
        "f":              "json",
    }

    for url in [
        "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query",
        "https://www.fws.gov/wetlandsmapper/rest/services/NWI/MapServer/0/query",
        "https://gis.michigan.gov/arcgis/rest/services/EGLE/NWI_Wetlands/MapServer/0/query",
    ]:
        try:
            r = requests.get(url, params=spatial_params, timeout=20, headers=HEADERS)
            if r.status_code != 200:
                continue
            data = r.json()
            if "error" in data:
                continue
            features = data.get("features", [])
            result["found"]         = len(features) > 0
            result["feature_count"] = len(features)
            result["source"]        = url
            for f in features:
                attrs = f.get("attributes", {})
                result["features"].append({
                    "wetland_type": attrs.get("WETLAND_TYPE", ""),
                    "attribute":    attrs.get("ATTRIBUTE", ""),
                    "acres":        attrs.get("ACRES", ""),
                })
            return result
        except Exception:
            continue

    result["found"]       = "UNKNOWN"
    result["manual_urls"] = [
        "https://www.michigan.gov/egle/maps-data/wetlands-map-viewer",
        "https://www.fws.gov/program/national-wetlands-inventory/wetlands-mapper",
    ]
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 5b. WETLANDS — GEOPANDAS SHAPEFILE (more reliable, ~100 MB download)
# ──────────────────────────────────────────────────────────────────────────────
def check_wetlands_geopandas(lat: float, lon: float, buffer_m: float = 100) -> dict:
    """
    Download Michigan NWI shapefile from USFWS and use geopandas to check.
    Requires: pip install geopandas shapely fiona
    Downloads ~100 MB on first run; cached to mi_nwi_cache/ afterward.
    """
    result: dict = {"found": None, "method": "geopandas", "features": []}

    try:
        import geopandas as gpd
        from shapely.geometry import Point

        cache_dir  = Path("mi_nwi_cache")
        shp_glob   = list(cache_dir.glob("*.shp")) if cache_dir.exists() else []

        if not shp_glob:
            nwi_url = (
                "https://www.fws.gov/wetlands/data/State-Downloads/"
                "MI_shapefile_wetlands.zip"
            )
            print("  Downloading Michigan NWI shapefile (~100 MB)…")
            r = requests.get(nwi_url, timeout=180, stream=True, headers=HEADERS)
            r.raise_for_status()

            cache_dir.mkdir(exist_ok=True)
            zip_path = cache_dir / "MI_wetlands.zip"
            with open(zip_path, "wb") as fh:
                for chunk in r.iter_content(8192):
                    fh.write(chunk)

            with zipfile.ZipFile(zip_path) as z:
                z.extractall(cache_dir)
            zip_path.unlink()
            shp_glob = list(cache_dir.glob("*.shp"))

        if not shp_glob:
            result["_error"]  = "No .shp file found in NWI download"
            result["_status"] = "FAILED"
            return result

        gdf   = gpd.read_file(shp_glob[0])
        point = gpd.GeoDataFrame(
            geometry=[Point(lon, lat)], crs="EPSG:4326"
        ).to_crs("EPSG:6497")  # Michigan State Plane
        gdf_proj = gdf.to_crs("EPSG:6497")

        nearby = gdf_proj[gdf_proj.geometry.intersects(
            point.geometry.buffer(buffer_m).iloc[0]
        )]

        result["found"]         = len(nearby) > 0
        result["feature_count"] = len(nearby)
        result["_source"]       = "USFWS NWI Shapefile (Michigan, cached)"

        for _, row in nearby.iterrows():
            result["features"].append({
                "wetland_type": row.get("WETLAND_TY", ""),
                "attribute":    row.get("ATTRIBUTE", ""),
                "acres":        row.get("ACRES", ""),
            })

    except ImportError as e:
        result["_error"]  = f"Missing: {e} — pip install geopandas shapely fiona"
        result["_status"] = "MISSING_DEPENDENCY"
    except Exception as e:
        result["_error"]  = str(e)
        result["_status"] = "FAILED"

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 6. FEMA NFHL — FLOOD ZONE
# ──────────────────────────────────────────────────────────────────────────────
def check_fema_flood(lat: float, lon: float) -> dict:
    """FEMA NFHL layer 28 — flood zone for coordinates."""
    result: dict = {"zone": None, "description": None, "in_sfha": None}
    try:
        r = requests.get(
            "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query",
            params={
                "geometry":       f"{lon},{lat}",
                "geometryType":   "esriGeometryPoint",
                "spatialRel":     "esriSpatialRelIntersects",
                "outFields":      "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
                "returnGeometry": "false",
                "inSR":           "4326",
                "f":              "json",
            },
            timeout=20, headers=HEADERS,
        )
        r.raise_for_status()
        features = r.json().get("features", [])
        if features:
            attrs              = features[0].get("attributes", {})
            zone               = attrs.get("FLD_ZONE", "X")
            result["zone"]     = zone
            result["zone_subtype"] = attrs.get("ZONE_SUBTY", "")
            result["in_sfha"]  = attrs.get("SFHA_TF") == "T"
            result["bfe"]      = attrs.get("STATIC_BFE")
            result["description"] = ZONE_DESCRIPTIONS.get(zone, f"Zone {zone}")
        else:
            result.update({
                "zone": "X", "in_sfha": False,
                "description": ZONE_DESCRIPTIONS["X"],
                "note": "No features returned — likely outside SFHA (or unmapped township)",
            })
    except Exception as e:
        result.update({
            "zone": "UNKNOWN", "error": str(e),
            "manual_url": "https://msc.fema.gov/portal/search",
            "note": (
                "~44% of Michigan townships are unmapped. "
                "Check floodfactor.com as alternative for unmapped areas."
            ),
        })
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 7. FEMA NATIONAL RISK INDEX — MULTI-HAZARD
# ──────────────────────────────────────────────────────────────────────────────
@retry(times=3, delay=2.0)
def get_fema_nri(lat: float, lon: float) -> dict:
    """
    County-level multi-hazard risk scores from FEMA NRI.
    Covers: riverine flooding, wildfire, tornado, ice storm, strong wind,
    hail, heat wave, drought, coastal flooding, earthquake, etc.
    Note: county-level data, not parcel-specific.
    """
    r = requests.get(
        "https://hazards.fema.gov/nri/api/v1/summary",
        params={"lat": lat, "lon": lon},
        timeout=20, headers=HEADERS,
    )
    r.raise_for_status()
    raw = r.json()

    keep = [
        "COUNTY", "STATE", "RISK_SCORE", "RISK_RATNG",
        "RFLD_RISKS", "RFLD_RATNG",   # riverine flooding
        "CFLD_RISKS", "CFLD_RATNG",   # coastal flooding
        "WFIR_RISKS", "WFIR_RATNG",   # wildfire
        "SWND_RISKS", "SWND_RATNG",   # strong wind
        "TRND_RISKS", "TRND_RATNG",   # tornado
        "HAIL_RISKS", "HAIL_RATNG",   # hail
        "ISTM_RISKS", "ISTM_RATNG",   # ice storm
        "HWAV_RISKS", "HWAV_RATNG",   # heat wave
        "DRGT_RISKS",                  # drought
    ]
    result = {k.lower(): raw[k] for k in keep if k in raw}
    result["_source"] = "FEMA NRI API (county-level)"
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 8. ZONING — REFS + PDF DOWNLOAD + PDFPLUMBER PARSE
# ──────────────────────────────────────────────────────────────────────────────
def get_zoning_refs() -> dict:
    return {
        "township":            "Pleasanton Township, Manistee County MI",
        "zoning_admin":        "Manistee County Planning Dept",
        "phone":               "(231) 929-5000",
        "address":             "415 3rd St, Manistee MI",
        "ordinance_2021_pdf":  (
            "https://pleasantontownship.org/uploads/1/1/3/9/"
            "113947797/2021__updated_pleasanton_township_zoning_ordinance.pdf"
        ),
        "zoning_map_2018_pdf": (
            "http://www.pleasantontownship.org/uploads/1/1/3/9/"
            "113947797/20180614_zoning_map.pdf"
        ),
        "master_plan_2025":    (
            "https://pleasantontownship.org/uploads/1/1/3/9/"
            "113947797/pleasanton_township_master_plan_2025_0908.pdf"
        ),
        "planning_mtg":        "2nd Monday each month, 6pm — 8958 Lumley Rd, Bear Lake MI",
        "dhd10_phone":         "(231) 876-3823",
        "_note": "Sub-district (RA-1/2/3) requires reviewing the 2018 zoning map PDF",
    }


def get_zoning_pdf_text(
    save_path: str = "pleasanton_zoning_2021.pdf",
) -> dict:
    """
    Download 2021 Pleasanton Township Zoning Ordinance and extract text.
    Searches for: RA sub-districts, setbacks, manufactured home rules,
    minimum lot sizes, wetland overlay references.
    Requires: pip install pdfplumber
    """
    url = (
        "https://pleasantontownship.org/uploads/1/1/3/9/"
        "113947797/2021__updated_pleasanton_township_zoning_ordinance.pdf"
    )
    result: dict = {"url": url, "_status": "NOT_STARTED"}

    try:
        r = requests.get(url, timeout=45, headers=HEADERS)
        r.raise_for_status()
        Path(save_path).write_bytes(r.content)
        result["saved"]       = save_path
        result["size_kb"]     = round(len(r.content) / 1024, 1)
        result["_status"]     = "DOWNLOADED"

        try:
            import pdfplumber

            with pdfplumber.open(save_path) as pdf:
                all_text = "\n".join(
                    (page.extract_text() or "") for page in pdf.pages
                )
                result["page_count"]  = len(pdf.pages)
            result["text_length"] = len(all_text)

            def _find(pattern: str, label: str, n: int = 5) -> list[str]:
                return [
                    m.strip()[:200]
                    for m in re.findall(pattern, all_text, re.IGNORECASE)
                ][:n]

            result["ra_districts"]          = _find(r'RA[-\s]?\d[^\n]{0,180}', "RA districts")
            result["setbacks"]              = _find(r'setback[^\n]{0,160}', "setbacks")
            result["manufactured_home_refs"] = _find(
                r'manufactured[^\n]{0,160}|mobile home[^\n]{0,160}', "mfg home"
            )
            result["minimum_lot_refs"]      = _find(
                r'minimum.{0,20}lot.{0,80}|lot.{0,20}area.{0,80}', "lot size"
            )
            result["wetland_refs"]          = _find(r'wetland[^\n]{0,160}', "wetlands")
            result["tiny_home_refs"]        = _find(r'tiny home[^\n]{0,160}', "tiny homes")
            result["_status"]               = "PARSED"

        except ImportError:
            result["_error"]  = "pdfplumber not installed — pip install pdfplumber"
            result["_status"] = "DOWNLOADED_NOT_PARSED"

    except Exception as e:
        result["_error"]  = str(e)
        result["_status"] = "FAILED"

    return result


# ──────────────────────────────────────────────────────────────────────────────
# 9. DEED / SALE HISTORY
# ──────────────────────────────────────────────────────────────────────────────
def get_deed_history(apn: str) -> dict:
    """
    Attempt to pull sale/transfer history from Manistee County portals.
    Michigan county deed portals vary widely in public accessibility.
    Falls back to providing manual contact info.
    """
    result: dict = {"transactions": [], "source": None}
    session = requests.Session()
    session.headers.update(HEADERS)

    attempts = [
        (
            "LIAA + history",
            "POST",
            "https://maps.liaa.org/manisteeparcels/propertysearch.asp",
            {"parcel": apn, "submit": "Search", "searchtype": "parcel", "history": "1"},
        ),
        (
            "Manistee Equalization",
            "GET",
            "https://www.manisteecountymi.gov/313/Equalization",
            None,
        ),
    ]

    for source_name, method, url, payload in attempts:
        try:
            if method == "POST":
                resp = session.post(url, data=payload, timeout=15)
            else:
                resp = session.get(url, timeout=15)

            soup = BeautifulSoup(resp.text, "lxml")

            # Generic table harvest — look for sale/deed keywords
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                    if any(re.search(r'sale|transfer|\$\d|deed|grantor|grantee', c, re.I)
                           for c in cells):
                        result["transactions"].append(cells)

            if result["transactions"]:
                result["source"] = source_name
                return result

        except Exception:
            continue

    result["_status"] = "NOT_ACCESSIBLE_ONLINE"
    result["_manual"] = {
        "name":    "Manistee County Register of Deeds",
        "address": "415 3rd St, Manistee MI 49660",
        "phone":   "(231) 723-3331",
        "note":    (
            "Michigan deed history often requires a county clerk visit or "
            "a paid service: PropStream ($99/mo), ATTOM, Regrid."
        ),
    }
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 10. DHD#10 — WELL/SEPTIC PERMIT LOOKUP
# ──────────────────────────────────────────────────────────────────────────────
def get_dhd10_permits(address: str) -> dict:
    """
    Attempt to locate well/septic permits from DHD#10 (Manistee County health dept).
    Most permit data requires a phone call or in-person request.
    """
    result: dict = {"permits": [], "found_portal": None}
    session = requests.Session()
    session.headers.update(HEADERS)

    base = "https://www.dhd10.org"
    try:
        r = session.get(f"{base}/homeowners/apply-for-a-new-wellseptic/", timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        # Collect any "search", "permit", "record" links on the page
        links = [
            (a.get_text(strip=True), a["href"])
            for a in soup.find_all("a", href=True)
            if re.search(r'search|permit|record|lookup|history', a.get("href", ""), re.I)
        ]
        result["page_links"] = [
            f"{base}{href}" if href.startswith("/") else href
            for _, href in links[:5]
        ]

        # Try a few known permit-search sub-paths
        for path in ["/permits/search", "/environmental-health/records", "/permits"]:
            try:
                pr = session.get(f"{base}{path}", timeout=10)
                if pr.status_code == 200 and len(pr.text) > 600:
                    result["found_portal"] = f"{base}{path}"
                    break
            except Exception:
                continue

    except Exception as e:
        result["_error"] = str(e)

    result["contact"] = {
        "phone":   "(231) 876-3823",
        "url":     base,
        "address": "385 Third St, Manistee MI 49660",
        "ask_for": (
            f"Well log and septic permit records for "
            f"APN 26101-1202140002 at {address}"
        ),
    }
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 11. LISTING PHOTOS + OPTIONAL VISION ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────
def get_listing_images(zpid: str = "106451402", mls: str = "25057116") -> dict:
    """
    Attempt to extract listing photo URLs via:
      1. Zillow GraphQL API
      2. Zillow page JSON (embedded data)
      3. Amplified RE (listing agent site)
    All major portals aggressively block bots — use --selenium for fallback.
    """
    result: dict = {"image_urls": [], "strategy": None}
    session = requests.Session()
    session.headers.update({**HEADERS, "Referer": "https://www.zillow.com/"})

    # Strategy 1: Zillow GraphQL
    try:
        payload = {
            "operationName": "ForSalePDP",
            "variables":     {"zpid": int(zpid)},
            "query": (
                "query ForSalePDP($zpid: ID!) { property(zpid: $zpid) "
                "{ photos { mixedSources { jpeg { url } } } } }"
            ),
        }
        r = session.post("https://www.zillow.com/graphql/",
                         json=payload, timeout=15)
        if r.status_code == 200:
            photos = (
                r.json().get("data", {})
                       .get("property", {})
                       .get("photos", [])
            )
            for p in photos:
                for src in p.get("mixedSources", {}).get("jpeg", []):
                    if src.get("url"):
                        result["image_urls"].append(src["url"])
            if result["image_urls"]:
                result["strategy"] = "Zillow GraphQL"
                return result
    except Exception:
        pass

    # Strategy 2: Zillow page — JSON embedded in <script> tags
    try:
        r = session.get(f"https://www.zillow.com/homes/{zpid}_zpid/", timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        for script in soup.find_all("script", type="application/json"):
            urls = re.findall(
                r'https://photos\.zillowstatic\.com/fp/[^"\'&]+', script.string or ""
            )
            result["image_urls"].extend(urls)
        if result["image_urls"]:
            result["strategy"] = "Zillow page JSON"
            result["image_urls"] = list(dict.fromkeys(result["image_urls"]))  # dedup
            return result
    except Exception:
        pass

    # Strategy 3: Amplified RE (listing agent site)
    try:
        amp_url = (
            f"https://www.amplifiedre.com/property/"
            f"15-{mls}-14638-Pleasanton-Highway-Bear-Lake-MI-49614"
        )
        r = session.get(amp_url, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            imgs = [
                img["src"] for img in soup.find_all("img", src=True)
                if re.search(r'\.(jpg|jpeg|png|webp)', img["src"], re.I)
                and "placeholder" not in img["src"].lower()
            ]
            if imgs:
                result["image_urls"] = imgs
                result["strategy"]   = "Amplified RE"
                return result
    except Exception:
        pass

    result["_status"] = "BLOCKED"
    result["_note"] = (
        "All portals blocked bot requests (HTTP 403). "
        "Use Selenium with a real Chrome profile:\n"
        "  from selenium import webdriver\n"
        f"  driver.get('https://www.zillow.com/homes/{zpid}_zpid/')\n"
        "  # then parse driver.page_source for photo URLs"
    )
    result["zillow_url"] = f"https://www.zillow.com/homes/{zpid}_zpid/"
    return result


def analyze_photo_vision(image_url: str, model: str = "gpt-4o") -> dict:
    """
    GPT-4o vision analysis of a property photo.
    Estimates structural condition, roof, foundation, age, visible damage.
    Requires: pip install openai  +  OPENAI_API_KEY env var.
    """
    result: dict = {"model": model, "image_url": image_url}
    try:
        import openai
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a licensed property inspector reviewing a photo "
                            "of a mobile/manufactured home. Return JSON with these keys: "
                            "structural_condition (poor|fair|good), roof_condition, "
                            "foundation_type (skirting|piers|concrete|unknown), "
                            "estimated_age_range (e.g. '1980-1995'), "
                            "visible_damage (list), cleanup_needed (none|minor|major), "
                            "asbestos_risk (low|medium|high — based on apparent age), "
                            "livable_estimate (yes|no|unclear), notes (string)."
                        ),
                    },
                    {"type": "image_url",
                     "image_url": {"url": image_url, "detail": "high"}},
                ],
            }],
            max_tokens=600,
        )
        content = resp.choices[0].message.content or ""
        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        try:
            result["analysis"] = json.loads(content)
        except json.JSONDecodeError:
            result["analysis_raw"] = content
        result["_status"] = "ANALYZED"
    except ImportError:
        result["_error"]  = "pip install openai  +  set OPENAI_API_KEY"
        result["_status"] = "MISSING_DEPENDENCY"
    except Exception as e:
        result["_error"]  = str(e)
        result["_status"] = "FAILED"
    return result


# ──────────────────────────────────────────────────────────────────────────────
# PROPERTY RESEARCHER CLASS
# ──────────────────────────────────────────────────────────────────────────────
class PropertyResearcher:
    """
    Orchestrates all due diligence checks.

    Usage:
        r = PropertyResearcher()
        r.run_all()
        r.save("bear_lake_data.json")

    Or from CLI:
        python bear_lake_scraper.py --selenium --geopandas --vision gpt-4o
    """

    def __init__(self, prop: dict | None = None):
        self.prop    = (prop or PROPERTY).copy()
        self.results = {
            "property": self.prop.copy(),
            "run_time": datetime.now().isoformat(),
        }

    # ── public API ──────────────────────────────────────────────────────────
    def run_all(
        self,
        use_selenium:  bool = False,
        use_geopandas: bool = False,
        vision_model:  str | None = None,
        skip:          list[str] | None = None,
    ) -> dict:
        skip = set(skip or [])

        print("=" * 60)
        print("  BEAR LAKE PROPERTY DUE DILIGENCE SCRAPER  v2.0")
        print(f"  {self.prop['address']}")
        print(f"  APN: {self.prop['apn']}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        self._step_geocode(skip)
        lat, lon, apn = self.prop["lat"], self.prop["lon"], self.prop["apn"]

        self._step_bsa(apn, use_selenium, skip)
        self._step_liaa(apn, skip)
        self._step_mi_parcel(apn, skip)
        self._step_wetlands(lat, lon, use_geopandas, skip)
        self._step_fema_flood(lat, lon, skip)
        self._step_fema_nri(lat, lon, skip)
        self._step_zoning_pdf(skip)
        self._step_deed_history(apn, skip)
        self._step_dhd10(skip)
        self._step_photos(vision_model, skip)

        self._print_summary()
        return self.results

    def save(self, path: str = "bear_lake_data.json") -> None:
        with open(path, "w") as fh:
            json.dump(self.results, fh, indent=2, default=str)
        print(f"\n  Saved → {path}")

    # ── steps ────────────────────────────────────────────────────────────────
    def _step_geocode(self, skip: set) -> None:
        if "geocode" in skip:
            return
        _section("1/11  Geocoding (US Census → Nominatim fallback)")
        lat, lon = geocode_address(self.prop["address"])
        if not lat:
            lat, lon = geocode_nominatim(self.prop["address"])
        if lat:
            self.prop["lat"], self.prop["lon"] = lat, lon
            print(f"  ✔ {lat:.6f}, {lon:.6f}")
        else:
            print(f"  ⚠ Using fallback: {self.prop['lat']}, {self.prop['lon']}")
        self.results["coordinates"] = {
            "lat":      self.prop["lat"],
            "lon":      self.prop["lon"],
            "geocoded": bool(lat),
        }

    def _step_bsa(self, apn: str, use_selenium: bool, skip: set) -> None:
        if "tax" in skip:
            return
        _section("2/11  BS&A tax records (Manistee County)")
        tax = get_bsa_tax(apn, self.prop["bsa_uid"])
        if use_selenium and tax.get("_status") in (
            "BLOCKED_OR_NO_RESULTS", "CONNECTION_ERROR"
        ):
            print("  → Requests blocked; trying Selenium…")
            tax_sel = get_bsa_tax_selenium(apn, self.prop["bsa_uid"])
            if "_error" not in tax_sel:
                tax = tax_sel
        _print_dict(tax)
        self.results["tax"] = tax

    def _step_liaa(self, apn: str, skip: set) -> None:
        if "parcel" in skip:
            return
        _section("3/11  LIAA parcel data (owner, acreage, legal desc)")
        parcel = get_liaa_parcel(apn)
        _print_dict(parcel)
        self.results["parcel"] = parcel

    def _step_mi_parcel(self, apn: str, skip: set) -> None:
        if "mi_parcel" in skip:
            return
        _section("4/11  Michigan GeoAPI / Manistee ArcGIS parcel")
        mi = get_mi_parcel_api(apn=apn, address=self.prop["address"])
        _print_dict(mi, max_items=8)
        self.results["mi_parcel"] = mi

    def _step_wetlands(
        self, lat: float, lon: float, use_geopandas: bool, skip: set
    ) -> None:
        if "wetlands" in skip:
            return
        _section(f"5/11  Wetlands check ({lat:.4f}, {lon:.4f})")
        if use_geopandas:
            w = check_wetlands_geopandas(lat, lon)
            if w.get("_status") in ("MISSING_DEPENDENCY", "DOWNLOAD_FAILED", "FAILED"):
                _warn(f"geopandas failed ({w.get('_error')}) — falling back to REST API")
                w = check_wetlands(lat, lon)
        else:
            w = check_wetlands(lat, lon)
        print(f"  Wetlands found: {w.get('found', 'UNKNOWN')}")
        for feat in w.get("features", [])[:3]:
            print(f"  Feature: {feat}")
        if w.get("manual_urls"):
            for u in w["manual_urls"]:
                print(f"  Manual: {u}")
        self.results["wetlands"] = w

    def _step_fema_flood(self, lat: float, lon: float, skip: set) -> None:
        if "flood" in skip:
            return
        _section("6/11  FEMA NFHL flood zone")
        flood = check_fema_flood(lat, lon)
        print(f"  Zone:        {flood.get('zone')}")
        print(f"  Description: {flood.get('description')}")
        print(f"  In SFHA:     {flood.get('in_sfha')}")
        if flood.get("note"):
            print(f"  Note:        {flood['note']}")
        if flood.get("error"):
            print(f"  Error:       {flood['error']}")
        self.results["flood"] = flood

    def _step_fema_nri(self, lat: float, lon: float, skip: set) -> None:
        if "nri" in skip:
            return
        _section("7/11  FEMA National Risk Index (county-level multi-hazard)")
        try:
            nri = get_fema_nri(lat, lon)
            _print_dict(nri, max_items=12)
        except Exception as e:
            nri = {"_error": str(e), "_manual": "https://hazards.fema.gov/nri/map"}
            print(f"  Error: {e}")
        self.results["fema_nri"] = nri

    def _step_zoning_pdf(self, skip: set) -> None:
        if "zoning" in skip:
            return
        _section("8/11  Pleasanton Township Zoning Ordinance PDF")
        zoning_pdf  = get_zoning_pdf_text()
        zoning_refs = get_zoning_refs()
        print(f"  Status:     {zoning_pdf.get('_status')}")
        print(f"  Size:       {zoning_pdf.get('size_kb', '?')} KB")
        print(f"  Text chars: {zoning_pdf.get('text_length', 0)}")
        for label, key in [
            ("RA district refs", "ra_districts"),
            ("Setback refs",     "setbacks"),
            ("Mfg home refs",    "manufactured_home_refs"),
        ]:
            refs = zoning_pdf.get(key, [])
            if refs:
                print(f"  {label} ({len(refs)}):")
                for r in refs[:2]:
                    print(f"    {r[:110]}")
        self.results["zoning_pdf"]  = zoning_pdf
        self.results["zoning_refs"] = zoning_refs

    def _step_deed_history(self, apn: str, skip: set) -> None:
        if "deed" in skip:
            return
        _section("9/11  Deed / sale history")
        deed = get_deed_history(apn)
        if deed.get("transactions"):
            print(f"  Found {len(deed['transactions'])} rows (source: {deed['source']})")
            for row in deed["transactions"][:3]:
                print(f"  {row}")
        else:
            print(f"  Not accessible online.")
            m = deed.get("_manual", {})
            if isinstance(m, dict):
                print(f"  {m.get('name')} — {m.get('phone')}")
        self.results["deed_history"] = deed

    def _step_dhd10(self, skip: set) -> None:
        if "dhd10" in skip:
            return
        _section("10/11  DHD#10 well/septic permit records")
        dhd10 = get_dhd10_permits(self.prop["address"])
        if dhd10.get("found_portal"):
            print(f"  Portal found: {dhd10['found_portal']}")
        else:
            print(f"  No online portal found.")
            print(f"  Call DHD#10: {dhd10['contact']['phone']}")
            print(f"  Ask for: {dhd10['contact']['ask_for']}")
        self.results["dhd10"] = dhd10

    def _step_photos(self, vision_model: str | None, skip: set) -> None:
        if "photos" in skip:
            return
        _section("11/11  Listing photos + vision analysis")
        photos = get_listing_images(
            zpid=self.prop["zpid"], mls=self.prop["mls"]
        )
        print(f"  Strategy:    {photos.get('strategy', 'BLOCKED')}")
        print(f"  Images found: {len(photos.get('image_urls', []))}")
        if photos.get("image_urls") and vision_model:
            print(f"  Analyzing first image with {vision_model}…")
            analysis = analyze_photo_vision(photos["image_urls"][0], vision_model)
            photos["vision_analysis"] = analysis
            if analysis.get("analysis"):
                _print_dict(analysis["analysis"], max_items=8)
        elif not photos.get("image_urls"):
            print(f"  Manual: {photos.get('zillow_url', '')}")
        self.results["photos"] = photos

    # ── summary ──────────────────────────────────────────────────────────────
    def _print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("  SUMMARY")
        print("=" * 60)

        def _st(key: str) -> str:
            d = self.results.get(key, {})
            if not d:
                return "─ SKIPPED "
            if d.get("_status") in (
                "FAILED", "NOT_ACCESSIBLE_ONLINE", "NOT_FOUND", "NOT_ACCESSIBLE"
            ) or d.get("_error"):
                return "✗ FAILED  "
            if d.get("_status") in ("BLOCKED_OR_NO_RESULTS", "CONNECTION_ERROR", "BLOCKED"):
                return "⚠ BLOCKED "
            if d.get("found") == "UNKNOWN":
                return "⚠ UNKNOWN "
            return "✔ OK      "

        rows = [
            ("Coordinates",             "coordinates"),
            ("Tax / assessed value",    "tax"),
            ("Parcel owner / acreage",  "parcel"),
            ("Michigan GeoAPI parcel",  "mi_parcel"),
            ("Wetlands on parcel",      "wetlands"),
            ("FEMA flood zone (NFHL)",  "flood"),
            ("FEMA NRI multi-hazard",   "fema_nri"),
            ("Zoning ordinance PDF",    "zoning_pdf"),
            ("Deed / sale history",     "deed_history"),
            ("DHD#10 permits",          "dhd10"),
            ("Listing photos",          "photos"),
        ]
        for label, key in rows:
            print(f"  {_st(key)} {label}")

        print("\n  ALWAYS MANUAL — no code can replace:")
        manual = [
            "Mobile home condition / age       → on-site inspector (~$300–$500)",
            "Well / water test                 → seller records or DHD#10: (231) 876-3823",
            "Septic condition / perc test      → seller records or DHD#10",
            "Natural gas at road               → Superior Energy: (231) 362-2520",
            "Road surface (paved vs gravel)    → Road Commission: (231) 723-3566",
            "RA sub-district confirmation      → 2018 zoning map PDF + county call",
            "Prior deed / sale history         → Manistee County Clerk: (231) 723-3331",
        ]
        for item in manual:
            print(f"  ✗ {item}")
        print("=" * 60)


# ──────────────────────────────────────────────────────────────────────────────
# LEGACY run() — kept for backward compatibility
# ──────────────────────────────────────────────────────────────────────────────
def run() -> dict:
    researcher = PropertyResearcher()
    results    = researcher.run_all()
    researcher.save("bear_lake_data.json")
    return results


# ──────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bear Lake property due diligence scraper v2.0"
    )
    parser.add_argument(
        "--selenium",    action="store_true",
        help="Enable Selenium fallback for JS-heavy sites (BS&A, LIAA)",
    )
    parser.add_argument(
        "--geopandas",   action="store_true",
        help="Download Michigan NWI shapefile and use geopandas for wetlands (~100 MB)",
    )
    parser.add_argument(
        "--vision",      metavar="MODEL", default=None,
        help="Enable GPT-4 vision photo analysis (e.g. --vision gpt-4o)",
    )
    parser.add_argument(
        "--skip",        nargs="*", default=[],
        metavar="STEP",
        help=(
            "Skip one or more steps: "
            "geocode tax parcel mi_parcel wetlands flood nri zoning deed dhd10 photos"
        ),
    )
    parser.add_argument(
        "--output",      default="bear_lake_data.json",
        help="Output JSON filename (default: bear_lake_data.json)",
    )
    args = parser.parse_args()

    researcher = PropertyResearcher()
    researcher.run_all(
        use_selenium  = args.selenium,
        use_geopandas = args.geopandas,
        vision_model  = args.vision,
        skip          = args.skip,
    )
    researcher.save(args.output)
