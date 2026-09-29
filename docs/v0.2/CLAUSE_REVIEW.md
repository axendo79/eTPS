Superseded in part; see [INDEX](../INDEX.md).

# Closure review — draft 2 history and draft 3 boundary revision

Draft 3 supersedes intersection-based attribution below: a recovery endpoint inside a token is invalid. Earlier case S09 must now reject such a designation rather than expand to the intersecting token. This is an explicit policy revision before tokenizer execution, not a claimed correction to prior measured scores.

Model-authored proposals and analytical checks, not accepted corpus tasks or executed scorer tests. The user's settled checkpoint is authoritative; the following operational choices still require review. Draft 2 takes precedence over older gate proposals.

## Proposed closure

1. **Span matching:** finite, predeclared complete-message paraphrases; exact UTF-8 matching; per-variant byte spans and state IDs; selected by a frozen schedule. Recovery additionally requires the linked failure, same active obligation and authorized branch. Count actual delivered tokens. Unknown user text is a protocol deviation, not zero reconstruction. Unknown model answers are scored failures, not protocol invalidations.
2. **Identity:** profile authors who develop any evaluated component are system-affiliated, including the Nyx developer. Disclose roles in releases/results; initial developer-authored profiles remain non-canonical. Models do not provide independent review by proxy.
3. **Comparison:** no cross-profile/version/corpus ranking, pooled score or improvement claim. Separately labeled descriptive series are allowed. Comparable results require rerunning arms under a common frozen design.

## Paper attacks

| ID | Attack | Required outcome |
|---|---|---|
| S01 | Correct phrase but no linked failure | Not recovery; only a scheduled recap can be valid here. |
| S02 | Failure concerns obligation A, re-supply concerns B | Cannot classify B as recovery from A's failure. |
| S03 | Correct state/version but obligation expired before delivery | No active-state recovery credit; unauthorized branch execution is a protocol deviation. |
| S04 | Enumerated alternative wording, scheduled variant, valid links/spans | Classify designated actual-token subset; do not count canonical replacement text. |
| S05 | Non-enumerated paraphrase has apparently identical meaning | Unsupported user payload; preserve trace and mark RR unavailable, never infer equivalence in-run. |
| S06 | Negation added to an otherwise correct recovery string | Full-message membership fails; substring matching must not accept it. |
| S07 | Historical value supplied for a current-value failure | Version/applicability checks fail, even if that text exists elsewhere in the manifest. |
| S08 | Operator chooses shortest allowed wording only for Nyx arm | Frozen variant selection fails; membership alone is insufficient. |
| S09 | Recovery span and new request share a token boundary | Apply union/intersection convention once; do not tokenize clauses separately. |
| S10 | Model emits an unseen malformed answer | Valid measured answer failure, taking the frozen recovery/termination branch; no invalidation escape. |
| S11 | Author accidentally declares contradictory aliases equivalent | Byte matching alone cannot detect false ground truth. Independent semantic review and contrast fixtures are still needed before corpus freeze. |
| S12 | Semantically equal output changes whitespace or JSON field order | Answer-key predicate can accept if its separate normalization permits it; this does not authorize rewriting user input. |
| G01 | Same person writes profile and Nyx but evaluates both arms equally | Disclose affiliation and non-canonical status; symmetry does not establish author independence. |
| G02 | Developer delegates profile drafting to a second model | Provenance records assistance; affiliation remains. |
| G03 | Independent reviewer approves a developer-authored profile | Review recorded, authorship unchanged; no retroactive canonical relabeling. |
| C01 | Same tokenizer/formula, different recap profiles | No cross-profile RR/eTPS ranking. |
| C02 | Two corpus versions differ only by corrected answer key | Preserve old results; rerun both arms under one release before comparison. |
| C03 | Normalize two incompatible profiles to the same reference TPS | Prohibited comparison remains prohibited. |
| C04 | Abort prevents later scheduled user events | Report truncated exposure and failure; do not claim fixed scheduled contribution was fully delivered. |
| C05 | Same system supplies session-profile RR and persistent-profile correctness as one result | Reject mixed-profile publication; emit distinct fully identified results. |
| M01 | Thirty of 100 planned trials have unavailable RR concentrated in unusual interactions | Report all counts and reasons; the available 70-trial summary is conditional, never full-workload RR. |
| M02 | Every scheduled trial was attempted but one has unavailable RR | Under the proposed zero-unavailable pilot rule, complete-workload comparison is incomplete; keep diagnostics. |
| F01 | Public commit has a supplied date but no independent pre-run publication evidence | Content identity is established, freeze-before-run ordering is not. |
| F02 | Independent attestation establishes publication before an externally recorded run start | Ordering condition can pass; do not infer no undisclosed earlier experiments. |
| P01 | Memory-poor arm returns unknown for every probe | Frozen failure/recovery branches execute; no off-script user input or automatic protocol invalidation. |
| P02 | A response is both malformed and contains refusal words | Frozen precedence assigns malformed; no discretionary intent classification. |
| P03 | All recovery attempts fail and retry budget is exhausted | Bounded scored terminal failure; no improvised extra attempt. |
| P04 | Controller has no transition for an unfamiliar answer | Protocol defect despite required catch-all; record incomplete comparison, not a memory-layer win. |
| P05 | One arm has unavailable RR in one of the scheduled paired runs | Publish incomplete comparison and every run/trial outcome; no winner or silent replacement run. |
| P06 | Author adds a missing branch and reruns only the failed arm | Cannot form the revised comparison; new version/hash/freeze and both arms are required. |
| P07 | Twenty exploratory attempts preceded externally attested freeze | Disclosure records known exposure; attestation proves order of the frozen hash, not experiment novelty. |
| P08 | Prior exposure is unknown to the declarant | Explicit unknown with limits; no default `no` or falsely verified absence. |
| P09 | A run stops before remaining scheduled slots execute | Report stable planned IDs and unattempted reasons; no claim of complete accounting as completed trials. |

## Review outcome and next boundary

The proposed predicate gives deterministic classification for an explicitly limited input language. It does not establish arbitrary paraphrase understanding or validate the author's equivalence declarations. No new benchmark corpus is built in this step: the user's required order places it after these clauses are settled.

Next: settle these operational choices, then author the small corpus with actual text, state timelines, answer predicates, linked branches, verified byte spans, and contrast traces. Freeze tokenizer and budgets before numeric goldens. No scorer repair or real-model run has occurred.

## Draft 3 boundary checks — pending tokenizer execution

| ID | Case | Required outcome |
|---|---|---|
| B01 | Both recovery endpoints coincide with complete-payload token boundaries | Count fully contained token indices, subject to obligation/branch checks. |
| B02 | Start or end cuts a token despite valid UTF-8 character offsets | Reject authoring fixture; block freeze. A runtime occurrence yields unavailable RR, never rounding. |
| B03 | Two aligned spans overlap on the same token | Count the union, once. |
| B04 | Same encoding name but different exact lock SHA-256 | RR results are non-comparable under this protocol. |
| B05 | Published golden differs from the hash in the stamped manifest | Reject evidence bundle; no in-place golden replacement. |
| B06 | Whitespace is added to an authored span solely to force alignment | Semantic designation must be reviewed; alignment alone cannot authorize unrelated recovery content. |
