"""
Generate CivicLens HTML report for John James.
Outputs report_john_james.html — open in any browser.
"""

from civic_lens import (
    build_john_james_profile,
    CIVICLENS_VERSION,
    VerificationStatus,
    IrregularityCategory,
)
from scorer import SPEC_VERSION
from datetime import date

# ─────────────────────────────────────────────────────────────
# FEC COMPLIANCE REVIEW ITEMS
# Patterns that warrant primary-source FEC review.
# None of the items below establish a violation — they identify
# patterns that a researcher or journalist should verify against
# primary FEC filings before drawing any conclusions.
# ─────────────────────────────────────────────────────────────

FEC_REVIEW_ITEMS = [
    {
        "title": "2020 Cycle Filing Deadline Compliance",
        "detail": (
            "The 2020 Senate cycle reportedly involved approximately $16.5M in receipts. "
            "FEC regulations require quarterly reports (11 CFR §104.5) and pre-election "
            "reports within 12 days of a general election. Whether all filing deadlines "
            "were met — and whether any amendments were filed — requires primary-source "
            "verification at fec.gov/data/filings."
        ),
        "source": "FEC filing rules, 11 CFR §104.5; verify at fec.gov/data/filings",
        "status": "requires_primary_verification",
        "note": "No violation established. Pattern warrants primary-source FEC review.",
    },
    {
        "title": "Outside Spending and Coordination Rules",
        "detail": (
            "Significant independent expenditures were publicly reported in support of "
            "James's 2020 Senate campaign. Federal law (52 U.S.C. §30116(a)(7)) prohibits "
            "coordination between candidate campaigns and independent expenditure-only "
            "committees (Super PACs). The records indicate no coordination has been "
            "established. This pattern requires independent FEC compliance review."
        ),
        "source": "52 U.S.C. §30116(a)(7); FEC coordination rules; fec.gov/legal-resources/",
        "status": "requires_primary_verification",
        "note": (
            "No coordination has been established. Outside spending in competitive "
            "Senate races is common and legal absent prohibited coordination."
        ),
    },
    {
        "title": "Recount-Period Campaign Finance Activity (Nov–Dec 2020)",
        "detail": (
            "Campaign finance receipts and expenditures during the November–December 2020 "
            "post-election period are publicly reportable under FEC rules. Whether any "
            "unusual or late-cycle transactions occurred during the period when a recount "
            "petition was under consideration requires primary-source review of FEC post-"
            "general and year-end filings."
        ),
        "source": "FEC post-general report period; fec.gov/data/filings — search 2020 year-end",
        "status": "requires_primary_verification",
        "note": (
            "No irregularity established. Post-election finance activity is publicly "
            "reported; pattern requires FEC primary-source review before any inference."
        ),
    },
    {
        "title": "Individual Contribution Limit Compliance",
        "detail": (
            "The 2020 election cycle individual contribution limit was $2,800 per election "
            "to a candidate committee (52 U.S.C. §30116(a)(1)(A)). In high-volume fundraising "
            "cycles (≈$16.5M reported), over-limit contributions sometimes require amended "
            "filings or refunds. Whether any amendment activity occurred requires primary-"
            "source FEC query of the James for Michigan committee filings."
        ),
        "source": "52 U.S.C. §30116(a)(1)(A); fec.gov/data/receipts — filter by committee",
        "status": "requires_primary_verification",
        "note": (
            "Over-limit contributions requiring amendment are common in high-volume cycles "
            "and do not establish a violation if properly remediated. Requires FEC review."
        ),
    },
]

STATUS_BADGE = {
    "requires_primary_verification": (
        '<span class="badge badge-review">REQUIRES FEC VERIFICATION</span>'
    ),
    "adjudicated_violation": (
        '<span class="badge badge-violation">ADJUDICATED VIOLATION</span>'
    ),
    "cleared": (
        '<span class="badge badge-clear">CLEARED</span>'
    ),
}


def verification_badge(v: VerificationStatus) -> str:
    classes = {
        VerificationStatus.VERIFIED:   "badge-verified",
        VerificationStatus.PROBABLE:   "badge-probable",
        VerificationStatus.CONTEXTUAL: "badge-contextual",
        VerificationStatus.UNVERIFIED: "badge-unverified",
    }
    return f'<span class="badge {classes[v]}">{v.value.upper()}</span>'


def irregularity_icon(cat: IrregularityCategory) -> str:
    icons = {
        IrregularityCategory.CLOSE_RACE:             "⚖",
        IrregularityCategory.RECOUNT_EVENT:          "🔁",
        IrregularityCategory.FUNDING_GEOGRAPHY:      "🗺",
        IrregularityCategory.INDUSTRY_CONCENTRATION: "🏭",
        IrregularityCategory.DONOR_CONCENTRATION:    "💰",
        IrregularityCategory.TIMING_OVERLAP:         "🕐",
        IrregularityCategory.DISCLOSURE_DELAY:       "⏳",
        IrregularityCategory.PAC_DEPENDENCE:         "🔗",
    }
    return icons.get(cat, "⚑")


def build_html(profile) -> str:
    today = date.today().isoformat()

    findings_html = ""
    for f in profile.findings:
        badge = verification_badge(f.verification)
        uncertainty = ""
        if f.uncertainty_note:
            uncertainty = f'<p class="uncertainty">⚠ {f.uncertainty_note}</p>'
        findings_html += f"""
        <div class="finding">
            {badge}
            <p class="claim">{f.claim}</p>
            <p class="source">Source: {f.provenance.to_citation()}</p>
            {uncertainty}
        </div>"""

    flags_html = ""
    for flag in profile.irregularity_flags:
        icon = irregularity_icon(flag.category)
        extra = ""
        if flag.requires_additional_context:
            extra = '<span class="badge badge-context">ADDITIONAL CONTEXT REQUIRED</span>'
        flags_html += f"""
        <div class="flag">
            <div class="flag-header">
                <span class="flag-icon">{icon}</span>
                <strong>{flag.category.value}</strong>
                {extra}
            </div>
            <p class="flag-desc">{flag.description}</p>
            <p class="source">Source: {flag.provenance.to_citation()}</p>
            <p class="severity-note">Note: {flag.severity_note}</p>
        </div>"""

    review_html = ""
    for item in FEC_REVIEW_ITEMS:
        badge_html = STATUS_BADGE.get(item["status"], "")
        review_html += f"""
        <div class="review-item">
            <div class="review-header">
                <span class="review-icon">⚑</span>
                <strong>{item["title"]}</strong>
                {badge_html}
            </div>
            <p class="review-detail">{item["detail"]}</p>
            <p class="source">Regulatory basis: {item["source"]}</p>
            <p class="severity-note">Note: {item["note"]}</p>
        </div>"""

    election_rows = ""
    for e in profile.election_history:
        parts = e.split(" — ", 1)
        year_race = parts[0]
        outcome = parts[1] if len(parts) > 1 else ""
        outcome_class = "outcome-win" if "Won" in outcome else "outcome-loss"
        election_rows += f"""
            <tr>
                <td class="el-race">{year_race}</td>
                <td class="{outcome_class}">{outcome}</td>
            </tr>"""

    committees_html = "".join(
        f'<li>{c}</li>' for c in profile.committee_assignments
    )
    pacs_html = "".join(
        f'<li>{p}</li>' for p in profile.affiliated_pacs
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CivicLens Report — {profile.name}</title>
<style>
  :root {{
    --cl-navy:    #0d1b2a;
    --cl-dark:    #1b2a3b;
    --cl-mid:     #243447;
    --cl-border:  #2e4057;
    --cl-text:    #e8edf2;
    --cl-muted:   #8ba0b5;
    --cl-accent:  #4fa3e0;
    --cl-green:   #2ecc71;
    --cl-yellow:  #f1c40f;
    --cl-orange:  #e67e22;
    --cl-red:     #e74c3c;
    --cl-purple:  #9b59b6;
    --cl-teal:    #1abc9c;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--cl-navy);
    color: var(--cl-text);
    font-size: 14px;
    line-height: 1.6;
  }}

  /* ── Header ── */
  header {{
    background: var(--cl-dark);
    border-bottom: 2px solid var(--cl-accent);
    padding: 20px 32px 16px;
    display: flex;
    align-items: flex-end;
    gap: 24px;
  }}
  .cl-wordmark {{
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--cl-accent);
    text-transform: uppercase;
  }}
  .cl-tagline {{
    font-size: 11px;
    color: var(--cl-muted);
    letter-spacing: 1px;
    text-transform: uppercase;
    padding-bottom: 2px;
  }}
  .cl-meta {{
    margin-left: auto;
    text-align: right;
    font-size: 11px;
    color: var(--cl-muted);
  }}

  /* ── Disclaimer banner ── */
  .disclaimer-banner {{
    background: #1a2a1a;
    border-left: 4px solid var(--cl-teal);
    padding: 12px 32px;
    font-size: 12px;
    color: #a8c8b0;
  }}
  .disclaimer-banner strong {{ color: var(--cl-teal); }}

  /* ── Layout ── */
  main {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 32px 24px 64px;
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 24px;
    align-items: start;
  }}

  /* ── Sidebar ── */
  .sidebar {{ display: flex; flex-direction: column; gap: 20px; }}

  .card {{
    background: var(--cl-dark);
    border: 1px solid var(--cl-border);
    border-radius: 8px;
    padding: 18px;
  }}
  .card-title {{
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--cl-accent);
    margin-bottom: 12px;
    font-weight: 600;
  }}
  .identity-name {{
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    line-height: 1.2;
    margin-bottom: 4px;
  }}
  .identity-office {{
    font-size: 13px;
    color: var(--cl-accent);
    margin-bottom: 10px;
  }}
  .identity-row {{
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid var(--cl-border);
    font-size: 12px;
  }}
  .identity-row:last-child {{ border-bottom: none; }}
  .identity-label {{ color: var(--cl-muted); }}
  .identity-value {{ color: var(--cl-text); font-weight: 500; text-align: right; max-width: 60%; }}

  .status-active {{
    display: inline-block;
    background: #1a3a2a;
    color: var(--cl-teal);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 3px;
    border: 1px solid var(--cl-teal);
    margin-bottom: 10px;
  }}

  .election-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 4px;
  }}
  .election-table td {{ padding: 5px 4px; border-bottom: 1px solid var(--cl-border); }}
  .el-race {{ color: var(--cl-muted); white-space: nowrap; padding-right: 8px; }}
  .outcome-win {{ color: var(--cl-green); }}
  .outcome-loss {{ color: #c0392b; }}

  ul.plain {{ list-style: none; padding: 0; }}
  ul.plain li {{
    font-size: 12px;
    color: var(--cl-muted);
    padding: 4px 0;
    border-bottom: 1px solid var(--cl-border);
  }}
  ul.plain li:last-child {{ border-bottom: none; }}

  /* ── Main content ── */
  .content {{ display: flex; flex-direction: column; gap: 28px; }}

  section h2 {{
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--cl-accent);
    margin-bottom: 14px;
    font-weight: 600;
    border-bottom: 1px solid var(--cl-border);
    padding-bottom: 6px;
  }}

  /* ── Badges ── */
  .badge {{
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding: 2px 7px;
    border-radius: 3px;
    text-transform: uppercase;
    margin-right: 6px;
  }}
  .badge-verified   {{ background: #1a3a1a; color: var(--cl-green);  border: 1px solid var(--cl-green); }}
  .badge-probable   {{ background: #3a2e00; color: var(--cl-yellow); border: 1px solid var(--cl-yellow); }}
  .badge-contextual {{ background: #2a2a1a; color: #c8b400;          border: 1px solid #c8b400; }}
  .badge-unverified {{ background: #2a1a1a; color: var(--cl-orange); border: 1px solid var(--cl-orange); }}
  .badge-review     {{ background: #2a1a00; color: var(--cl-orange); border: 1px solid var(--cl-orange); }}
  .badge-violation  {{ background: #2a0000; color: var(--cl-red);    border: 1px solid var(--cl-red); }}
  .badge-clear      {{ background: #1a3a1a; color: var(--cl-green);  border: 1px solid var(--cl-green); }}
  .badge-context    {{ background: #1a1a2a; color: var(--cl-purple); border: 1px solid var(--cl-purple); }}

  /* ── Findings ── */
  .finding {{
    background: var(--cl-dark);
    border: 1px solid var(--cl-border);
    border-left: 3px solid var(--cl-border);
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 10px;
  }}
  .finding:has(.badge-verified)   {{ border-left-color: var(--cl-green); }}
  .finding:has(.badge-probable)   {{ border-left-color: var(--cl-yellow); }}
  .finding:has(.badge-contextual) {{ border-left-color: #c8b400; }}
  .finding:has(.badge-unverified) {{ border-left-color: var(--cl-orange); }}
  .claim {{ margin: 6px 0 6px; font-size: 13px; line-height: 1.5; }}
  .source {{ font-size: 11px; color: var(--cl-muted); font-family: monospace; }}
  .uncertainty {{ font-size: 11px; color: var(--cl-yellow); margin-top: 6px; background: #2a2600; padding: 6px 8px; border-radius: 4px; }}

  /* ── Flags ── */
  .flag {{
    background: var(--cl-mid);
    border: 1px solid var(--cl-orange);
    border-left: 4px solid var(--cl-orange);
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .flag-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }}
  .flag-icon {{ font-size: 16px; }}
  .flag-desc {{ font-size: 13px; line-height: 1.5; margin-bottom: 6px; }}
  .severity-note {{ font-size: 11px; color: var(--cl-teal); margin-top: 6px; background: #0d2a25; padding: 6px 8px; border-radius: 4px; }}

  /* ── FEC Review Items ── */
  .review-item {{
    background: #1a1200;
    border: 1px solid var(--cl-orange);
    border-left: 4px solid var(--cl-red);
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .review-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }}
  .review-icon {{ font-size: 16px; color: var(--cl-orange); }}
  .review-detail {{ font-size: 13px; line-height: 1.5; margin-bottom: 6px; color: #d4c090; }}
  .no-violation-box {{
    background: #0a1a0a;
    border: 1px solid var(--cl-teal);
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 20px;
    font-size: 12px;
    color: #a8c8b0;
  }}
  .no-violation-box strong {{ color: var(--cl-teal); }}

  /* ── Sources ── */
  .source-list {{ list-style: none; padding: 0; }}
  .source-list li {{
    padding: 6px 0;
    border-bottom: 1px solid var(--cl-border);
    font-size: 12px;
    color: var(--cl-muted);
    font-family: monospace;
  }}
  .source-list li:last-child {{ border-bottom: none; }}
  .source-list a {{ color: var(--cl-accent); text-decoration: none; }}
  .source-list a:hover {{ text-decoration: underline; }}

  /* ── Footer ── */
  footer {{
    background: var(--cl-dark);
    border-top: 1px solid var(--cl-border);
    padding: 20px 32px;
    font-size: 11px;
    color: var(--cl-muted);
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }}
  footer .footer-warning {{
    color: #a8c8b0;
    max-width: 700px;
  }}

  /* ── Summary metrics ── */
  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 4px;
  }}
  .metric {{
    background: var(--cl-mid);
    border: 1px solid var(--cl-border);
    border-radius: 6px;
    padding: 10px 12px;
    text-align: center;
  }}
  .metric-value {{ font-size: 24px; font-weight: 700; color: var(--cl-accent); }}
  .metric-label {{ font-size: 10px; color: var(--cl-muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }}
  .metric-value.orange {{ color: var(--cl-orange); }}
  .metric-value.yellow {{ color: var(--cl-yellow); }}
  .metric-value.red    {{ color: var(--cl-red); }}
</style>
</head>
<body>

<header>
  <div>
    <div class="cl-wordmark">CivicLens</div>
    <div class="cl-tagline">Evidence-First Civic Research</div>
  </div>
  <div class="cl-meta">
    Report generated: {today}<br>
    Profile version: {CIVICLENS_VERSION} &nbsp;|&nbsp; eTPS spec: {SPEC_VERSION}<br>
    Status: PRE-PUBLICATION — verify all figures before release
  </div>
</header>

<div class="disclaimer-banner">
  <strong>IMPORTANT:</strong>
  This report is based solely on publicly available records. Patterns and flags do not imply
  coordination, improper conduct, illegality, or wrongdoing. No adjudicated violations are
  established. All FEC figures require primary-source verification at fec.gov before publication.
  No person is accused of any crime or ethics violation by this report.
</div>

<main>
  <!-- ── Sidebar ── -->
  <aside class="sidebar">

    <div class="card">
      <div class="card-title">Identity</div>
      <div class="status-active">● INCUMBENT</div>
      <div class="identity-name">{profile.name}</div>
      <div class="identity-office">{profile.office}</div>
      <div class="identity-row">
        <span class="identity-label">Jurisdiction</span>
        <span class="identity-value">{profile.jurisdiction}</span>
      </div>
      <div class="identity-row">
        <span class="identity-label">Party</span>
        <span class="identity-value">{profile.party}</span>
      </div>
      <div class="identity-row">
        <span class="identity-label">Current status</span>
        <span class="identity-value">{profile.current_status}</span>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Election History</div>
      <table class="election-table">
        {election_rows}
      </table>
    </div>

    <div class="card">
      <div class="card-title">Committee Assignments</div>
      <ul class="plain">
        {committees_html}
      </ul>
    </div>

    <div class="card">
      <div class="card-title">Affiliated Committees / PACs</div>
      <ul class="plain">
        {pacs_html}
      </ul>
    </div>

    <div class="card">
      <div class="card-title">Report Summary</div>
      <div class="metrics-grid">
        <div class="metric">
          <div class="metric-value">{len(profile.findings)}</div>
          <div class="metric-label">Findings</div>
        </div>
        <div class="metric">
          <div class="metric-value orange">{len(profile.irregularity_flags)}</div>
          <div class="metric-label">Flags</div>
        </div>
        <div class="metric">
          <div class="metric-value yellow">{len(FEC_REVIEW_ITEMS)}</div>
          <div class="metric-label">FEC Review</div>
        </div>
      </div>
    </div>

  </aside>

  <!-- ── Main content ── -->
  <div class="content">

    <section>
      <h2>Research Findings</h2>
      {findings_html}
    </section>

    <section>
      <h2>Irregularity Flags</h2>
      <div class="no-violation-box">
        <strong>Methodology note:</strong> Flags identify patterns from public records only.
        They do not establish wrongdoing, coordination, or illegality.
        Each flag requires independent primary-source verification before any inference is drawn.
        The absence of a flag does not mean no pattern exists — only that none was identified
        within the scope of this profile.
      </div>
      {flags_html}
    </section>

    <section>
      <h2>FEC Compliance Review — Patterns Warranting Investigation</h2>
      <div class="no-violation-box">
        <strong>No violations established.</strong>
        The items below identify regulatory patterns that a researcher, journalist, or
        watchdog organization should verify against primary FEC filings. None of these
        items constitute a finding of a campaign finance violation. All require
        primary-source review at fec.gov before any conclusion can be drawn.
      </div>
      {review_html}
    </section>

    <section>
      <h2>Source References</h2>
      <ul class="source-list">
        <li>FEC campaign finance filings — <a href="https://www.fec.gov/data/" target="_blank">fec.gov/data/</a></li>
        <li>FEC legal resources &amp; regulations — <a href="https://www.fec.gov/legal-resources/" target="_blank">fec.gov/legal-resources/</a></li>
        <li>U.S. House official records — <a href="https://clerk.house.gov/" target="_blank">clerk.house.gov/</a></li>
        <li>Michigan SOS certified election results — <a href="https://mvic.sos.state.mi.us/" target="_blank">mvic.sos.state.mi.us/</a></li>
        <li>CourtListener (federal court records) — <a href="https://www.courtlistener.com/" target="_blank">courtlistener.com/</a></li>
        <li>FEC individual receipts search — <a href="https://www.fec.gov/data/receipts/individual-contributions/" target="_blank">fec.gov/data/receipts/individual-contributions/</a></li>
        <li>FEC committee filings — <a href="https://www.fec.gov/data/filings/" target="_blank">fec.gov/data/filings/</a></li>
        <li>Outside spending (independent expenditures) — <a href="https://www.fec.gov/data/independent-expenditures/" target="_blank">fec.gov/data/independent-expenditures/</a></li>
      </ul>
    </section>

  </div>
</main>

<footer>
  <div class="footer-warning">
    CivicLens {CIVICLENS_VERSION} — Evidence-first civic research.
    This document is based entirely on publicly available records.
    No person named herein is accused of any crime, ethics violation, or improper conduct.
    Patterns identified require independent verification. Not for publication without
    primary-source corroboration of all figures marked PROBABLE or requiring FEC verification.
  </div>
  <div>Generated {today} &nbsp;|&nbsp; eTPS spec {SPEC_VERSION}</div>
</footer>

</body>
</html>"""


if __name__ == "__main__":
    profile = build_john_james_profile()
    html = build_html(profile)

    out_path = "report_john_james.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written to {out_path}")
    print(f"  Findings:     {len(profile.findings)}")
    print(f"  Flags:        {len(profile.irregularity_flags)}")
    print(f"  FEC review:   {len(FEC_REVIEW_ITEMS)}")
    print(f"  Language check: {profile.language_check() or 'CLEAN'}")
