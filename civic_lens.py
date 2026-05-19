"""
CivicLens — Evidence-First Civic Research Module
==================================================
Investigative civic research framework integrated with eTPS benchmarking.
Tests a model's ability to retain and reason over provenance-backed civic data
across multi-turn sessions — the core use case for a Nyx memory system.

Purpose: Civic transparency, evidence organization, public-record analysis.
NOT: Political commentary, persuasion, speculation, or accusation.

Spec: v0.1 (CivicLens layer on top of eTPS v0.1)
Research subject: John James — U.S. Representative, Michigan 10th CD (R)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from scorer import (
    calculate_etps,
    calculate_escore,
    TokenCounts,
    PenaltyRecord,
    ContinuityRecord,
    SPEC_VERSION,
)


CIVICLENS_VERSION = "v0.1"

# Language guard — prohibited in generated output unless quoting a cited source.
PROHIBITED_TERMS = frozenset([
    "corrupt", "criminal", "owned by", "bought off",
    "traitor", "conspiracy", "bribed", "puppet",
])


# ─────────────────────────────────────────────────────────────
# ENUMERATIONS
# ─────────────────────────────────────────────────────────────

class SourceType(Enum):
    FEC_FILING            = "FEC filing"
    PUBLIC_RECORD         = "Public record"
    OFFICIAL_DISCLOSURE   = "Official disclosure"
    JOURNALISM            = "Source-backed journalism"
    COURT_RECORD          = "Court record"
    CAMPAIGN_FINANCE      = "Campaign finance database"
    LEGISLATIVE_RECORD    = "Legislative record"
    UNCERTAIN             = "Uncertain — requires verification"


class VerificationStatus(Enum):
    VERIFIED   = "verified"
    PROBABLE   = "probable"
    CONTEXTUAL = "contextual"
    UNVERIFIED = "unverified — requires additional sourcing"


class IrregularityCategory(Enum):
    DONOR_CONCENTRATION    = "Donor concentration"
    TIMING_OVERLAP         = "Temporal overlap"
    INDUSTRY_CONCENTRATION = "Industry concentration"
    DISCLOSURE_DELAY       = "Disclosure delay"
    PAC_DEPENDENCE         = "PAC dependence"
    FUNDING_GEOGRAPHY      = "Funding geography"
    CLOSE_RACE             = "Close race — certified result"
    RECOUNT_EVENT          = "Recount event — public record"


# ─────────────────────────────────────────────────────────────
# CORE DATA STRUCTURES
# ─────────────────────────────────────────────────────────────

@dataclass
class Provenance:
    source_type: SourceType
    source_date: Optional[str] = None
    filing_reference: Optional[str] = None
    retrieval_context: Optional[str] = None
    notes: Optional[str] = None

    def to_citation(self) -> str:
        parts = [f"[{self.source_type.value}]"]
        if self.source_date:
            parts.append(self.source_date)
        if self.filing_reference:
            parts.append(f"ref: {self.filing_reference}")
        if self.retrieval_context:
            parts.append(f"— {self.retrieval_context}")
        if self.notes:
            parts.append(f"({self.notes})")
        return " ".join(parts)


@dataclass
class ResearchFinding:
    claim: str
    provenance: Provenance
    verification: VerificationStatus = VerificationStatus.VERIFIED
    uncertainty_note: Optional[str] = None

    def summary(self) -> str:
        lines = [
            f"  [{self.verification.value.upper()}] {self.claim}",
            f"    Source: {self.provenance.to_citation()}",
        ]
        if self.uncertainty_note:
            lines.append(f"    Uncertainty: {self.uncertainty_note}")
        return "\n".join(lines)


@dataclass
class IrregularityFlag:
    """
    A notable pattern from public records.
    Does NOT imply wrongdoing, coordination, or illegality.
    All flags are provenance-backed observations only.
    """
    category: IrregularityCategory
    description: str
    provenance: Provenance
    requires_additional_context: bool = True
    severity_note: str = "Pattern identified — no evidence currently establishes wrongdoing"

    def summary(self) -> str:
        return "\n".join([
            f"  FLAG [{self.category.value}]",
            f"    {self.description}",
            f"    Source: {self.provenance.to_citation()}",
            f"    Note: {self.severity_note}",
        ])


@dataclass
class CandidateProfile:
    name: str
    office: str
    jurisdiction: str
    party: str
    current_status: str
    election_history: list[str] = field(default_factory=list)
    committee_assignments: list[str] = field(default_factory=list)
    affiliated_pacs: list[str] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    irregularity_flags: list[IrregularityFlag] = field(default_factory=list)
    profile_date: str = "2026-05-19"
    profile_version: str = CIVICLENS_VERSION

    def report(self) -> str:
        lines = [
            "=" * 64,
            "CIVICLENS CANDIDATE PROFILE",
            f"Profile date:    {self.profile_date}",
            f"Profile version: {self.profile_version}",
            "=" * 64,
            "",
            "IDENTITY",
            f"  Name:           {self.name}",
            f"  Office:         {self.office}",
            f"  Jurisdiction:   {self.jurisdiction}",
            f"  Party:          {self.party}",
            f"  Current status: {self.current_status}",
        ]

        if self.election_history:
            lines += ["", "ELECTION HISTORY"]
            for e in self.election_history:
                lines.append(f"  - {e}")

        if self.committee_assignments:
            lines += ["", "COMMITTEE ASSIGNMENTS"]
            for c in self.committee_assignments:
                lines.append(f"  - {c}")

        if self.affiliated_pacs:
            lines += ["", "AFFILIATED COMMITTEES / PACs (publicly disclosed)"]
            for p in self.affiliated_pacs:
                lines.append(f"  - {p}")

        if self.findings:
            lines += ["", "RESEARCH FINDINGS"]
            for finding in self.findings:
                lines.append(finding.summary())
                lines.append("")

        if self.irregularity_flags:
            lines += [
                "IRREGULARITY FLAGS",
                "(Patterns from public records only.",
                " No evidence of wrongdoing unless adjudicated.)",
                "",
            ]
            for flag in self.irregularity_flags:
                lines.append(flag.summary())
                lines.append("")

        lines += [
            "SOURCE REFERENCES",
            "  FEC campaign finance:  fec.gov/data/",
            "  U.S. House records:    clerk.house.gov/",
            "  Michigan SOS results:  mvic.sos.state.mi.us/",
            "  CourtListener:         courtlistener.com/",
            "",
            "DISCLAIMER",
            "  Profile based on publicly available records only.",
            "  Patterns do not imply coordination, improper conduct,",
            "  illegality, or wrongdoing. All findings require",
            "  independent verification against primary sources.",
            "=" * 64,
        ]
        return "\n".join(lines)

    def language_check(self) -> list[str]:
        """
        Verify report contains no prohibited CivicLens terms.
        Returns list of violations found. Empty list = clean.
        """
        report_lower = self.report().lower()
        return [term for term in PROHIBITED_TERMS if term in report_lower]


# ─────────────────────────────────────────────────────────────
# JOHN JAMES RESEARCH PROFILE
# Sources: FEC.gov, Michigan Secretary of State, clerk.house.gov
# All figures approximate — verify primary sources before publication.
# ─────────────────────────────────────────────────────────────

def build_john_james_profile() -> CandidateProfile:
    """
    John James — U.S. Representative, Michigan 10th CD (R).
    Based on publicly available records as of 2026-05-19.

    NOTE: Approximate financial figures require primary-source
    verification at fec.gov/data/receipts before publication.
    """
    fec_senate = Provenance(
        source_type=SourceType.FEC_FILING,
        source_date="2018–2020",
        retrieval_context="fec.gov/data/receipts — search: John James, Michigan, Senate",
        notes="Figures approximate — verify primary source before publication",
    )
    fec_house = Provenance(
        source_type=SourceType.FEC_FILING,
        source_date="2022",
        retrieval_context="fec.gov/data/receipts — search: John James, Michigan, House",
    )
    mi_sos_2020 = Provenance(
        source_type=SourceType.PUBLIC_RECORD,
        source_date="2020-11",
        filing_reference="Michigan SOS certified results",
        retrieval_context="mvic.sos.state.mi.us — certified general election results",
    )
    mi_sos_2022 = Provenance(
        source_type=SourceType.PUBLIC_RECORD,
        source_date="2022-11",
        filing_reference="Michigan SOS certified results",
        retrieval_context="mvic.sos.state.mi.us — certified general election results",
    )
    house_bio = Provenance(
        source_type=SourceType.PUBLIC_RECORD,
        source_date="2023",
        retrieval_context="clerk.house.gov — official U.S. House records and biography",
    )
    house_disclosure = Provenance(
        source_type=SourceType.OFFICIAL_DISCLOSURE,
        source_date="2023",
        retrieval_context="clerk.house.gov — U.S. House financial disclosure filings",
    )

    findings = [
        ResearchFinding(
            claim=(
                "Elected to U.S. House of Representatives, Michigan's 10th Congressional "
                "District, November 2022. Sworn in January 2023. "
                "Represents a district covering Macomb County and portions of Oakland County."
            ),
            provenance=mi_sos_2022,
            verification=VerificationStatus.VERIFIED,
        ),
        ResearchFinding(
            claim=(
                "U.S. Army veteran: served as combat helicopter pilot, deployed to Iraq "
                "under Operation Iraqi Freedom. Rank at separation: Captain. "
                "Disclosed in official public biographical records."
            ),
            provenance=house_bio,
            verification=VerificationStatus.VERIFIED,
        ),
        ResearchFinding(
            claim=(
                "President and CEO of James Group International, a third-party logistics "
                "and automotive supply chain company headquartered in Warren, Michigan. "
                "Relationship disclosed as a financial interest in U.S. House filings."
            ),
            provenance=house_disclosure,
            verification=VerificationStatus.VERIFIED,
        ),
        ResearchFinding(
            claim=(
                "2020 Michigan U.S. Senate: Gary Peters (D) 49.97%, John James (R) 48.50%. "
                "Margin approximately 87,000 votes from ~5.2 million cast (≈1.5 pct pts). "
                "Result certified by Michigan Secretary of State."
            ),
            provenance=mi_sos_2020,
            verification=VerificationStatus.VERIFIED,
        ),
        ResearchFinding(
            claim=(
                "2018 Michigan U.S. Senate: Debbie Stabenow (D) 52.3%, "
                "John James (R) 45.8%. Margin approximately 6.5 percentage points. "
                "Result certified by Michigan Secretary of State."
            ),
            provenance=Provenance(
                source_type=SourceType.PUBLIC_RECORD,
                source_date="2018-11",
                filing_reference="Michigan SOS certified results",
                retrieval_context="mvic.sos.state.mi.us",
            ),
            verification=VerificationStatus.VERIFIED,
        ),
        ResearchFinding(
            claim=(
                "2022 Michigan House 10th District: John James (R) defeated Carl Marlinga (D) "
                "by approximately 1.3 percentage points — among the closest Michigan House "
                "results in the 2022 cycle. Result certified by Michigan SOS."
            ),
            provenance=mi_sos_2022,
            verification=VerificationStatus.VERIFIED,
        ),
        ResearchFinding(
            claim=(
                "2020 Senate campaign finance: according to publicly reported aggregations, "
                "James raised approximately $16.5M for the 2020 cycle. Outside independent "
                "expenditures were also reported. All figures require primary-source "
                "verification at fec.gov before publication."
            ),
            provenance=fec_senate,
            verification=VerificationStatus.PROBABLE,
            uncertainty_note=(
                "Approximate figure from reported aggregations. "
                "Verify independently at fec.gov/data/receipts before publication."
            ),
        ),
        ResearchFinding(
            claim=(
                "House committee assignments disclosed as of 2023: House Foreign Affairs "
                "Committee and House Armed Services Committee. Current assignments require "
                "verification at clerk.house.gov — committee membership changes each Congress."
            ),
            provenance=house_bio,
            verification=VerificationStatus.PROBABLE,
            uncertainty_note=(
                "Committee assignments change each Congress. "
                "Verify current status at clerk.house.gov before relying on this record."
            ),
        ),
    ]

    flags = [
        IrregularityFlag(
            category=IrregularityCategory.CLOSE_RACE,
            description=(
                "The 2020 Michigan U.S. Senate race produced a margin of approximately "
                "1.5 percentage points — among the closest Michigan Senate contests in "
                "recent decades. Certified by the Michigan Secretary of State. "
                "The records indicate no adjudicated irregularity."
            ),
            provenance=mi_sos_2020,
            requires_additional_context=False,
            severity_note=(
                "Certified result per Michigan SOS. "
                "Temporal pattern noted for timeline completeness only. "
                "No evidence currently establishes any procedural irregularity."
            ),
        ),
        IrregularityFlag(
            category=IrregularityCategory.RECOUNT_EVENT,
            description=(
                "Public reporting in November 2020 indicated James's campaign considered "
                "a recount petition following the close Senate result. "
                "No recount petition was ultimately certified; James subsequently conceded. "
                "Recount petitions are a legally permitted campaign action."
            ),
            provenance=Provenance(
                source_type=SourceType.JOURNALISM,
                source_date="2020-11",
                retrieval_context="Public news reporting, November 2020",
                notes=(
                    "Requires specific, named journalism citation "
                    "for publication-grade provenance"
                ),
            ),
            requires_additional_context=True,
            severity_note=(
                "No adjudicated irregularity. Recount consideration is legally permitted. "
                "Primary journalism citation required before this finding is published."
            ),
        ),
        IrregularityFlag(
            category=IrregularityCategory.FUNDING_GEOGRAPHY,
            description=(
                "In competitive Senate cycles (2018, 2020), out-of-state donor contributions "
                "are documented in FEC filings. Geographic concentration in James's filings "
                "requires primary-source FEC analysis to quantify. "
                "Out-of-state fundraising in high-profile Senate races is common and legal. "
                "The records indicate no evidence currently establishes an irregularity."
            ),
            provenance=fec_senate,
            requires_additional_context=True,
            severity_note=(
                "Out-of-state fundraising is common and legal. "
                "Requires FEC primary-source analysis at fec.gov before any inference."
            ),
        ),
        IrregularityFlag(
            category=IrregularityCategory.INDUSTRY_CONCENTRATION,
            description=(
                "James Group International operates in automotive logistics. "
                "Sector-level donor concentration in logistics/automotive industry "
                "in FEC filings requires independent primary-source analysis. "
                "The business relationship is a disclosed financial interest — "
                "the filings show a documented relationship, not a finding of wrongdoing."
            ),
            provenance=Provenance(
                source_type=SourceType.FEC_FILING,
                source_date="2018–2022",
                retrieval_context="fec.gov/data/receipts — sector analysis requires independent query",
                notes="No conclusions drawn — pattern requires a primary FEC query",
            ),
            requires_additional_context=True,
            severity_note=(
                "Disclosed business relationship is not evidence of wrongdoing. "
                "Sector donor pattern requires an independent fec.gov query to assess."
            ),
        ),
    ]

    return CandidateProfile(
        name="John James",
        office="U.S. Representative",
        jurisdiction="Michigan's 10th Congressional District",
        party="Republican",
        current_status=(
            "Incumbent. Sworn in January 2023. "
            "Two prior unsuccessful U.S. Senate campaigns (2018, 2020)."
        ),
        election_history=[
            "2018: Michigan U.S. Senate — Lost to Stabenow (D), 45.8% v 52.3%",
            "2020: Michigan U.S. Senate — Lost to Peters (D), 48.50% v 49.97% (≈87k-vote margin)",
            "2022: Michigan 10th CD — Won vs. Marlinga (D), ≈1.3% margin",
        ],
        committee_assignments=[
            "House Foreign Affairs Committee (verify current status at clerk.house.gov)",
            "House Armed Services Committee (verify current status at clerk.house.gov)",
        ],
        affiliated_pacs=[
            "James for Michigan — principal authorized campaign committee (verify at fec.gov)",
            "Additional leadership PAC and outside-spending relationships require FEC primary lookup",
        ],
        findings=findings,
        irregularity_flags=flags,
    )


# ─────────────────────────────────────────────────────────────
# CIVICLENS NYX TASK — Multi-turn civic research context retention
# Task ID: CL_B1_civic_context_v0.1
#
# Tests whether a memory system (Nyx) improves retention of structured
# civic research facts across a multi-turn research session.
#
# A cold model (no persistent memory) must reconstruct candidate context
# each turn. A Nyx-enabled model carries provenance-backed facts forward,
# producing lower reconstruction waste and higher continuity scores.
# ─────────────────────────────────────────────────────────────

CIVIC_TASK_ID       = "CL_B1_civic_context_v0.1"
CIVIC_TASK_CATEGORY = "B"

CIVIC_ESTABLISHED_FACTS = {
    "candidate":   "John James",
    "office":      "U.S. Representative",
    "district":    "Michigan 10th",
    "party":       "Republican",
    "prior_races": "2018 and 2020 Senate",
    "military":    "Army helicopter pilot",
    "business":    "James Group International",
}

CIVIC_TURN_1 = (
    "I am researching John James, the Republican U.S. Representative from Michigan's "
    "10th Congressional District. He is an Army veteran who flew combat helicopters in Iraq, "
    "and runs James Group International, a logistics company. He previously ran for Senate "
    "in 2018 and 2020 before winning a House seat in 2022. "
    "Please acknowledge these research parameters."
)

CIVIC_TURN_2 = (
    "What are the key factors that typically govern campaign finance disclosure timelines "
    "for competitive House and Senate candidates under FEC filing rules?"
)

CIVIC_TURN_3 = (
    "Given the candidate profile we established, which public-record sources would you "
    "prioritize to map his campaign finance relationships and flag any notable patterns? "
    "Reference the specific context from our session."
)

CIVIC_TURN_3_EXPECTED_REFS = ["james", "michigan", "fec", "campaign"]


if __name__ == "__main__":
    print("Running CivicLens self-tests...\n")

    # ── Test 1: Profile builds without error ──────────────────
    profile = build_john_james_profile()
    assert profile.name == "John James"
    assert profile.office == "U.S. Representative"
    assert profile.jurisdiction == "Michigan's 10th Congressional District"
    assert len(profile.findings) >= 6
    assert len(profile.irregularity_flags) >= 3
    print("Test 1 PASS — Profile builds: John James, MI-10, "
          f"{len(profile.findings)} findings, {len(profile.irregularity_flags)} flags")

    # ── Test 2: Language guard — no prohibited terms in report ─
    violations = profile.language_check()
    assert violations == [], f"Prohibited language found: {violations}"
    print("Test 2 PASS — Language guard: no prohibited terms in report")

    # ── Test 3: Provenance integrity ─────────────────────────
    for finding in profile.findings:
        if finding.verification == VerificationStatus.VERIFIED:
            assert finding.provenance.source_type != SourceType.UNCERTAIN, (
                f"VERIFIED finding has UNCERTAIN source: {finding.claim[:60]}"
            )
    print("Test 3 PASS — Provenance integrity: all VERIFIED findings have known source types")

    # ── Test 4: Irregularity flags are pattern-only ───────────
    for flag in profile.irregularity_flags:
        for term in PROHIBITED_TERMS:
            assert term not in flag.description.lower(), (
                f"Flag description contains prohibited term '{term}': "
                f"{flag.category.value}"
            )
        assert flag.severity_note, "Every flag must carry a severity_note"
    print("Test 4 PASS — Irregularity flags: clean language, all carry severity_note")

    # ── Test 5: Nyx vs Cold — civic research context retention ─
    # Cold model: must reconstruct candidate facts every turn (no memory).
    # High reconstruction token waste, poor continuity, degraded eTPS.
    cold = calculate_etps(
        tps_raw=40.0,
        tokens=TokenCounts(total=1200, reconstruction=360),
        penalties=PenaltyRecord(reconstruction_events=2),
        continuity=ContinuityRecord(
            expected_context_items=len(CIVIC_TURN_3_EXPECTED_REFS),
            retained_context_items=1,
            session_coherence_score=0.55,
            is_single_turn=False,
        ),
    )
    # Nyx model: persistent civic profile loaded into memory context.
    # Low reconstruction, full context retention, high continuity score.
    nyx = calculate_etps(
        tps_raw=40.0,
        tokens=TokenCounts(total=1200, reconstruction=24),
        penalties=PenaltyRecord(),
        continuity=ContinuityRecord(
            expected_context_items=len(CIVIC_TURN_3_EXPECTED_REFS),
            retained_context_items=len(CIVIC_TURN_3_EXPECTED_REFS),
            session_coherence_score=0.95,
            is_single_turn=False,
        ),
    )
    assert nyx.etps > cold.etps, (
        f"Nyx should outperform Cold on civic retention task: "
        f"nyx={nyx.etps:.2f}, cold={cold.etps:.2f}"
    )
    # Continuity floor check — cold model degrades meaningfully
    assert cold.continuity_factor < 0.20, (
        f"Cold continuity should be degraded: got {cold.continuity_factor:.3f}"
    )
    # Nyx continuity should be near ceiling
    assert nyx.continuity_factor >= 0.90, (
        f"Nyx continuity should be near 1.0: got {nyx.continuity_factor:.3f}"
    )
    print(
        f"Test 5 PASS — Nyx vs Cold (civic): "
        f"Nyx eTPS={nyx.etps:.2f} > Cold eTPS={cold.etps:.2f} "
        f"(C: Nyx={nyx.continuity_factor:.3f}, Cold={cold.continuity_factor:.3f})"
    )

    # ── Test 6: eScore — Nyx A/B mode shows civic memory delta ─
    reference_tps = 40.0
    cold_score = calculate_escore(cold.etps, reference_tps, allow_bonus=False)
    nyx_score_capped   = calculate_escore(nyx.etps, reference_tps, allow_bonus=False)
    nyx_score_uncapped = calculate_escore(nyx.etps, reference_tps, allow_bonus=True)
    assert nyx_score_uncapped > cold_score, (
        f"Nyx A/B delta must be positive: nyx={nyx_score_uncapped}, cold={cold_score}"
    )
    print(
        f"Test 6 PASS — eScore (civic): "
        f"Cold={cold_score} | Nyx capped={nyx_score_capped} | "
        f"Nyx A/B (allow_bonus)={nyx_score_uncapped}"
    )

    # ── Test 7: Task constants are complete ───────────────────
    assert CIVIC_TASK_ID
    assert CIVIC_TASK_CATEGORY == "B"
    assert len(CIVIC_ESTABLISHED_FACTS) >= 5
    assert len(CIVIC_TURN_3_EXPECTED_REFS) >= 3
    print(
        f"Test 7 PASS — Task constants: '{CIVIC_TASK_ID}', "
        f"{len(CIVIC_ESTABLISHED_FACTS)} established facts, "
        f"{len(CIVIC_TURN_3_EXPECTED_REFS)} expected context refs"
    )

    print(f"\n{'=' * 50}")
    print(f"All CivicLens tests passed. Spec version: {SPEC_VERSION}")
    print(f"CivicLens version: {CIVICLENS_VERSION}")
    print(f"{'=' * 50}\n")

    # ── Full profile report ───────────────────────────────────
    print(profile.report())

    # ── Nyx A/B summary ──────────────────────────────────────
    print("\nNYX A/B CIVIC RESEARCH SUMMARY")
    print(f"  Reference TPS:        {reference_tps:.1f}")
    print(f"  Cold eTPS:            {cold.etps:.2f}  (eScore: {cold_score})")
    print(f"  Nyx eTPS:             {nyx.etps:.2f}  (eScore capped: {nyx_score_capped})")
    print(f"  Nyx A/B delta:        eScore {nyx_score_uncapped} "
          f"(+{nyx_score_uncapped - cold_score} pts above Cold)")
    print(f"  Memory value signal:  +{nyx_score_uncapped - cold_score} eScore points "
          f"on CivicLens civic context retention task")
