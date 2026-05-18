#!/usr/bin/env python3
"""
Bear Lake Property Due Diligence Scraper
=========================================
Property : 14638 Pleasanton Hwy, Bear Lake (Pleasanton Twp), MI 49614
Parcel   : 26101-1202140002
Run      : python bear_lake_scraper.py

Automated checks:
  1. US Census Geocoder       — lat/lon (free, no key)
  2. BS&A Online              — taxes, SEV, taxable value, owner
  3. Manistee County LIAA     — parcel boundaries, acreage, owner
  4. USFWS NWI / EGLE         — wetland presence (critical risk check)
  5. FEMA NFHL                — flood zone designation
  6. Pleasanton Twp zoning    — reference links (PDF must be read manually)

Still requires manual action:
  - Mobile home condition/age → on-site inspector
  - Well log / septic permit  → seller records or DHD#10
  - Natural gas at road       → call Superior Energy (231) 362-2520
  - Road surface type         → call Road Commission (231) 723-3566
  - Exact RA sub-district     → review 2018 zoning map PDF

Install:
  pip install requests beautifulsoup4 lxml
  pip install selenium undetected-chromedriver  # optional Selenium fallback
"""

import json
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# Property constants
# ─────────────────────────────────────────────────────────────────────────────
PROPERTY = {
    "address":  "14638 Pleasanton Hwy, Bear Lake, MI 49614",
    "apn":      "26101-1202140002",
    "bsa_uid":  "2022",        # Manistee County BS&A client ID
    "lat":      44.4330,       # fallback if geocoder fails
    "lon":      -86.1430,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

ZONE_DESCRIPTIONS = {
    "X":  "✔ Minimal flood hazard — outside 500-year flood plain",
    "X500": "Moderate risk — within 500-year flood plain",
    "A":  "⚠ HIGH RISK — SFHA, 100-year flood plain (no BFE)",
    "AE": "⚠ HIGH RISK — SFHA, 100-year flood plain with BFE",
    "AH": "⚠ HIGH RISK — Shallow flooding 1-3 ft",
    "AO": "⚠ HIGH RISK — Sheet-flow flooding 1-3 ft",
    "VE": "⚠ HIGH RISK — Coastal with wave action",
    "V":  "⚠ HIGH RISK — Coastal with wave action (no BFE)",
    "D":  "Undetermined flood hazard",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Geocoder — US Census (free, no API key)
# ─────────────────────────────────────────────────────────────────────────────
def geocode_address(address: str) -> tuple[float | None, float | None]:
    """Return (lat, lon) via US Census geocoder."""
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {
        "address":   address,
        "benchmark": "Public_AR_Current",
        "format":    "json",
    }
    try:
        r = requests.get(url, params=params, timeout=15, headers=HEADERS)
        r.raise_for_status()
        matches = r.json().get("result", {}).get("addressMatches", [])
        if matches:
            c = matches[0]["coordinates"]
            return float(c["y"]), float(c["x"])
    except Exception as e:
        _warn(f"Geocoder error: {e}")
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# 2. BS&A Online — Tax Records
# ─────────────────────────────────────────────────────────────────────────────
def get_bsa_tax(apn: str, uid: str = "2022") -> dict:
    """
    Query BS&A Online for Manistee County parcel tax data.
    BS&A is a session-heavy ASP.NET site; this tries a direct POST.
    Falls back to Selenium instructions if blocked.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    base = "https://bsaonline.com"

    result = {}
    try:
        # Load search page — harvest CSRF token
        page = session.get(f"{base}/?uid={uid}", timeout=15)
        soup = BeautifulSoup(page.text, "lxml")
        token_tag = soup.find("input", {"name": "__RequestVerificationToken"})
        token = token_tag["value"] if token_tag else ""

        time.sleep(1.2)

        # POST parcel search
        payload = {
            "__RequestVerificationToken": token,
            "SearchType":                 "Parcel",
            "ParcelNumber":               apn,
            "uid":                        uid,
        }
        resp = session.post(
            f"{base}/SiteSearch/TaxRecordSearch?uid={uid}",
            data=payload,
            timeout=20,
        )
        soup2 = BeautifulSoup(resp.text, "lxml")

        # Harvest label-value pairs from the result table
        for row in soup2.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key and val and len(key) < 60:
                    result[key] = val

        if not result:
            # Site may require JS rendering — try extracting any visible text blocks
            for tag in soup2.find_all(class_=lambda c: c and "value" in str(c).lower()):
                label_tag = tag.find_previous(class_=lambda c: c and "label" in str(c).lower())
                if label_tag:
                    result[label_tag.get_text(strip=True)] = tag.get_text(strip=True)

        if result:
            result["_source"] = "BS&A Online (requests)"
        else:
            result["_status"] = "BLOCKED_OR_NO_RESULTS"
            result["_manual_url"] = f"https://bsaonline.com/?uid={uid}"
            result["_tip"] = (
                "BS&A requires JavaScript or a Selenium session. "
                "Run get_bsa_tax_selenium() below, or open the URL manually "
                f"and search parcel {apn}."
            )

    except Exception as e:
        result["_error"] = str(e)
        result["_status"] = "CONNECTION_ERROR"

    return result


def get_bsa_tax_selenium(apn: str, uid: str = "2022") -> dict:
    """
    Selenium fallback for BS&A (handles JS-heavy rendering).
    Requires:  pip install selenium undetected-chromedriver
    """
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

        # Locate parcel search field (selector may vary by BS&A version)
        selectors = [
            "input[name*='arcel']",
            "#parcelNumber",
            "input[placeholder*='arcel']",
            "input[id*='arcel']",
        ]
        search_input = None
        for sel in selectors:
            try:
                search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                break
            except Exception:
                continue

        if not search_input:
            driver.quit()
            return {"_error": "Could not find parcel search input on BS&A page"}

        search_input.clear()
        search_input.send_keys(apn)

        # Submit
        btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
        btn.click()
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "lxml")
        driver.quit()

        result = {}
        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key and val and len(key) < 80:
                    result[key] = val

        result["_source"] = "BS&A Online (Selenium)"
        return result

    except ImportError:
        return {
            "_error": "Selenium not installed.",
            "_install": "pip install selenium undetected-chromedriver",
        }
    except Exception as e:
        return {"_error": f"Selenium failed: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Manistee County LIAA Parcel Viewer
# ─────────────────────────────────────────────────────────────────────────────
def get_liaa_parcel(apn: str) -> dict:
    """
    Query Manistee County's LIAA parcel search portal.
    Returns owner, legal description, acreage, etc.
    """
    result = {}
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        url = "https://maps.liaa.org/manisteeparcels/propertysearch.asp"
        # Fetch the form page first
        page = session.get(url, timeout=15)
        soup = BeautifulSoup(page.text, "lxml")

        time.sleep(1)

        # POST parcel search
        payload = {"parcel": apn, "submit": "Search", "searchtype": "parcel"}
        resp = session.post(url, data=payload, timeout=20)
        soup2 = BeautifulSoup(resp.text, "lxml")

        # Parse result tables
        for row in soup2.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).rstrip(":")
                val = cells[1].get_text(strip=True)
                if key and val and key != val and len(key) < 80:
                    result[key] = val

        # Also try definition lists
        for dt in soup2.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                result[dt.get_text(strip=True)] = dd.get_text(strip=True)

        if result:
            result["_source"] = "Manistee County LIAA"
        else:
            result["_status"] = "NO_RESULTS"
            result["_manual_url"] = url
            result["_tip"] = f"Open {url} and search parcel {apn}"

    except Exception as e:
        result["_error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. Wetlands — USFWS NWI + Michigan EGLE fallback
# ─────────────────────────────────────────────────────────────────────────────
def check_wetlands(lat: float, lon: float, buffer_m: int = 100) -> dict:
    """
    Check NWI wetland features within buffer_m meters of the property centroid.
    Uses USFWS NWI MapServer first, then Michigan EGLE as fallback.
    """
    result: dict = {"found": None, "features": [], "source": None}

    # USFWS NWI — layer 0 is NWI polygons
    endpoints = [
        "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query",
        "https://www.fws.gov/wetlandsmapper/rest/services/NWI/MapServer/0/query",
    ]

    spatial_params = {
        "geometry":          f"{lon},{lat}",
        "geometryType":      "esriGeometryPoint",
        "spatialRel":        "esriSpatialRelIntersects",
        "distance":          buffer_m,
        "units":             "esriSRUnit_Meter",
        "inSR":              "4326",
        "outFields":         "WETLAND_TYPE,ATTRIBUTE,ACRES,Shape_Area",
        "returnGeometry":    "false",
        "f":                 "json",
    }

    for url in endpoints:
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

    # Michigan EGLE GIS fallback
    mi_url = "https://gis.michigan.gov/arcgis/rest/services/EGLE/NWI_Wetlands/MapServer/0/query"
    try:
        r = requests.get(mi_url, params=spatial_params, timeout=20, headers=HEADERS)
        if r.status_code == 200:
            data = r.json()
            features = data.get("features", [])
            result["found"]         = len(features) > 0
            result["feature_count"] = len(features)
            result["source"]        = "Michigan EGLE GIS"
            for f in features:
                result["features"].append(f.get("attributes", {}))
            return result
    except Exception:
        pass

    result["found"]       = "UNKNOWN"
    result["manual_urls"] = [
        "https://www.mcgi.state.mi.us/wetlands/textSearch.html",
        "https://www.michigan.gov/egle/maps-data/wetlands-map-viewer",
        "https://www.fws.gov/program/national-wetlands-inventory/wetlands-mapper",
    ]
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. FEMA NFHL — Flood Zone
# ─────────────────────────────────────────────────────────────────────────────
def check_fema_flood(lat: float, lon: float) -> dict:
    """
    Query FEMA NFHL layer 28 (Flood Hazard Zones) for the property coordinates.
    Returns zone, SFHA flag, and human-readable description.
    """
    result: dict = {"zone": None, "description": None, "in_sfha": None}

    url = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"
    params = {
        "geometry":       f"{lon},{lat}",
        "geometryType":   "esriGeometryPoint",
        "spatialRel":     "esriSpatialRelIntersects",
        "outFields":      "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
        "returnGeometry": "false",
        "inSR":           "4326",
        "f":              "json",
    }

    try:
        r = requests.get(url, params=params, timeout=20, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        features = data.get("features", [])
        if features:
            attrs       = features[0].get("attributes", {})
            zone        = attrs.get("FLD_ZONE", "X")
            sfha        = attrs.get("SFHA_TF", "F")   # T = in SFHA, F = not
            result["zone"]        = zone
            result["zone_subtype"]= attrs.get("ZONE_SUBTY", "")
            result["in_sfha"]     = sfha == "T"
            result["bfe"]         = attrs.get("STATIC_BFE")
            result["description"] = ZONE_DESCRIPTIONS.get(zone, f"Zone {zone}")
        else:
            result["zone"]        = "X"
            result["in_sfha"]     = False
            result["description"] = ZONE_DESCRIPTIONS["X"]
            result["note"]        = "No features returned — property likely outside SFHA"
    except Exception as e:
        result["zone"]       = "UNKNOWN"
        result["error"]      = str(e)
        result["manual_url"] = "https://msc.fema.gov/portal/search"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 6. Zoning reference — Pleasanton Township
# ─────────────────────────────────────────────────────────────────────────────
def get_zoning_refs() -> dict:
    return {
        "township":             "Pleasanton Township, Manistee County MI",
        "zoning_admin":         "Manistee County Planning Dept",
        "phone":                "(231) 929-5000",
        "address":              "415 3rd St, Manistee MI",
        "ordinance_pdf":        "https://manisteecountymi.gov/DocumentCenter/View/1201/Pleasanton-Township-Zoning-Ordinance-PDF",
        "zoning_map_2018_pdf":  "http://www.pleasantontownship.org/uploads/1/1/3/9/113947797/20180614_zoning_map.pdf",
        "planning_mtg":         "2nd Monday each month, 6pm — 8958 Lumley Rd, Bear Lake MI",
        "dhd10_well_septic":    "https://www.dhd10.org/homeowners/apply-for-a-new-wellseptic/",
        "dhd10_phone":          "(231) 876-3823",
        "note":                 "Sub-district (RA-1/2/3) requires reviewing the 2018 zoning map PDF",
        "_status":              "MANUAL_REVIEW_REQUIRED",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _warn(msg: str) -> None:
    print(f"  ⚠ {msg}", file=sys.stderr)


def _section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def run() -> dict:
    print("=" * 60)
    print(" BEAR LAKE PROPERTY DUE DILIGENCE SCRAPER")
    print(f" {PROPERTY['address']}")
    print(f" APN: {PROPERTY['apn']}")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    report: dict = {"property": PROPERTY.copy(), "run_time": datetime.now().isoformat()}

    # ── 1. Geocode
    _section("1/6  Geocoding address (US Census)")
    lat, lon = geocode_address(PROPERTY["address"])
    if lat and lon:
        PROPERTY["lat"], PROPERTY["lon"] = lat, lon
        print(f"  ✔ {lat:.6f}, {lon:.6f}")
    else:
        print(f"  Using fallback: {PROPERTY['lat']}, {PROPERTY['lon']}")
    report["coordinates"] = {"lat": PROPERTY["lat"], "lon": PROPERTY["lon"]}

    # ── 2. BS&A
    _section("2/6  BS&A tax records (Manistee County)")
    tax = get_bsa_tax(PROPERTY["apn"], PROPERTY["bsa_uid"])
    if tax.get("_status") in ("BLOCKED_OR_NO_RESULTS", "CONNECTION_ERROR"):
        print("  → Requests blocked — trying Selenium fallback…")
        tax_sel = get_bsa_tax_selenium(PROPERTY["apn"], PROPERTY["bsa_uid"])
        tax = tax_sel if "_error" not in tax_sel else tax
    for k, v in tax.items():
        print(f"  {k}: {v}")
    report["tax"] = tax

    # ── 3. LIAA Parcel
    _section("3/6  LIAA parcel data (owner, acreage, description)")
    parcel = get_liaa_parcel(PROPERTY["apn"])
    for k, v in list(parcel.items())[:12]:
        print(f"  {k}: {v}")
    report["parcel"] = parcel

    # ── 4. Wetlands
    _section(f"4/6  NWI / EGLE wetlands check  ({PROPERTY['lat']:.4f}, {PROPERTY['lon']:.4f})")
    wetlands = check_wetlands(PROPERTY["lat"], PROPERTY["lon"], buffer_m=100)
    found_str = str(wetlands.get("found", "UNKNOWN"))
    print(f"  Wetlands found: {found_str}")
    if wetlands.get("features"):
        for feat in wetlands["features"]:
            print(f"  Feature: {feat}")
    if wetlands.get("manual_urls"):
        print("  Manual verification URLs:")
        for u in wetlands["manual_urls"]:
            print(f"    {u}")
    report["wetlands"] = wetlands

    # ── 5. FEMA
    _section("5/6  FEMA NFHL flood zone")
    flood = check_fema_flood(PROPERTY["lat"], PROPERTY["lon"])
    print(f"  Zone       : {flood.get('zone')}")
    print(f"  Description: {flood.get('description')}")
    print(f"  In SFHA    : {flood.get('in_sfha')}")
    if flood.get("error"):
        print(f"  Error: {flood['error']}")
        print(f"  Manual: {flood.get('manual_url')}")
    report["flood"] = flood

    # ── 6. Zoning refs
    _section("6/6  Zoning references (Pleasanton Township)")
    zoning = get_zoning_refs()
    for k, v in zoning.items():
        if not k.startswith("_"):
            print(f"  {k}: {v}")
    report["zoning"] = zoning

    # ── Summary
    print("\n" + "=" * 60)
    print(" SUMMARY — WHAT AUTOMATION CAN & CANNOT RESOLVE")
    print("=" * 60)

    auto_status = {
        "Coordinates (geocoded)":   "✔ RESOLVED" if report["coordinates"]["lat"] != 44.4330 else "⚠ FALLBACK",
        "Tax / assessed value":     "✔ RESOLVED" if (report["tax"] and "_status" not in report["tax"]) else "✗ MANUAL NEEDED",
        "Parcel owner / acreage":   "✔ RESOLVED" if (report["parcel"] and "_status" not in report["parcel"]) else "✗ MANUAL NEEDED",
        "Wetlands on parcel":       "✔ RESOLVED" if report["wetlands"]["found"] is not None and report["wetlands"]["found"] != "UNKNOWN" else "✗ MANUAL NEEDED",
        "FEMA flood zone":          "✔ RESOLVED" if report["flood"].get("zone") not in (None, "UNKNOWN") else "✗ MANUAL NEEDED",
    }

    for item, status in auto_status.items():
        print(f"  {status:<22} {item}")

    print("\n  ALWAYS REQUIRE MANUAL ACTION (no code can replace):")
    manual_items = [
        "Mobile home condition / age         → on-site licensed inspector",
        "Well condition / water test          → seller records or DHD#10",
        "Septic condition / permit records    → seller records or DHD#10",
        "Natural gas at this address          → call Superior Energy (231) 362-2520",
        "Road surface (paved vs. gravel)      → call Road Commission (231) 723-3566",
        "Exact RA zoning sub-district         → review 2018 zoning map PDF",
        "Prior sale history / deed            → Manistee County Clerk",
    ]
    for item in manual_items:
        print(f"  ✗ {item}")

    print("=" * 60)

    # ── Save output
    out_file = "bear_lake_data.json"
    with open(out_file, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\n  Data saved → {out_file}")

    return report


if __name__ == "__main__":
    run()
