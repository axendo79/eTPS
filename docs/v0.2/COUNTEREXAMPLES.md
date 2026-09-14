# eTPS v0.2 counterexample review

Authorship/provenance: Codex authored the case formulations, illustrative numbers and expected outcomes from user requirements and supplied critiques. All cases are model-proposed analytical fixtures, not observed model behavior, independent reviewer findings, or executed tests. See [PROVENANCE](PROVENANCE.md) for decision status and source limitations.

2026-09-14. Analytical attacks on draft 0, not executed software tests. The baseline remains ea51ce82e011c7e65bdc43e9d5af923cdcec4897. This document does not claim an independent review.

| Attack or fixture | Required classification / finding |
|---|---|
| Retained fact: establish database=SQLite, then ask its value | Exact correct value passes; probe itself is not reconstruction. |
| Keyword trap: answer database=Postgres while mentioning SQLite | First-attempt retention fails regardless of keywords; take frozen recovery branch. |
| Confident wrong answer, no recovery before timeout | R can be 0. Correctness gate fails; RR=0 never means successful retention. |
| Failed recall followed by scripted SQLite re-supply | Only designated active-state recovery spans enter R; pre-recovery failure remains visible after successful correction. |
| Update database from SQLite to Postgres | Update is new state, R=0. Subsequent old value fails a current-state question. |
| Ask for the original database after the update | SQLite remains correct if historical retention is separately obligated. Supersession cannot erase all history. |
| Two equally authoritative contradictory dates | Expected answer is unresolved plus specified alternatives or legitimate clarification; choosing one without support fails. |
| Newly arrived evidence changes an earlier conclusion | New evidence/update is not reconstruction, even if delivered with “Actually.” |
| Clarification asks for a never-established unit | R=0; valid only under the frozen ambiguity rule. |
| Model asks for the already-established unit | Frozen recovery branch applies, R includes active unit re-supply. Wording alone cannot distinguish this from legitimate clarification. |
| Context pressure evicts an obligated fact | Obligation survives declared eviction; failure is observable. A vendor cannot terminate it by choosing a smaller internal cache. |
| Scheduled voluntary recap of known state | R=0 under draft's narrowed recovery definition. The original candidate wording alone would count it: this is a substantive unresolved definition choice. |
| Re-supply occurs exactly at expiration boundary | End is exclusive: R=0 for the expired obligation. Check event-phase ordering explicitly. |
| Request concerns out-of-contract state | R=0; do not expand obligations after seeing failure. Task correctness may still fail if a final assertion was independently required. |
| Mixed message repeats old date and adds a new location | Only the old-date recovery span counts. Token crossing a span boundary follows the frozen intersection rule. |
| Two active obligations share the same recovery token | Count union of token indices, never count twice. |
| Client resends entire history on every request | No added user input in I or R for transport replay. Provider input/retrieval costs are reported separately. |
| System inserts a long internal summary | Cannot dilute I, and is not user re-supply. Record its tokens and latency separately. |
| System requests irrelevant extra details to dilute RR | Harness cannot invent helpful extra user events; unauthorized requests take frozen failure/termination branches. |
| Vendor changes obligations after a poor run | Invalid run/version combination, not improved RR. |
| Corpus author selects only tasks favorable to one architecture | Freezing does not fix selection bias. Non-canonical status and independent corpus review remain necessary. |
| Negative R, R>I, NaN timing, missing usage | Reject invalid fields or mark unavailable; never estimate or clamp to pass. |
| No probes, no measured input, or no raw timing | Relevant metrics/gates unavailable; do not report a perfect score. |
| Runner drops failed trials before computing median | Report every attempted trial and failure/eligibility counts; survivor-only success claims prohibited. |
| Scorer saves only rounded aggregate results | Insufficient for faithful replay; preserve original events, counts, and timings. |

## Formula attacks with explicit arithmetic

**Denominator dilution.** At TPS=50, R=100 and I=1,000, RR=0.10 and candidate eTPS=45. Add 9,000 unrelated user tokens: R is unchanged but eTPS rises to 49.5. Frozen prompts prevent systems from freely exploiting this within a profile, but profile authors can still influence the index. Cross-profile ranking is not justified.

**Retrieval cost reversal.** A: TPS=50, RR=0.10, candidate eTPS=45. B: TPS=50, RR=0, candidate eTPS=50, but B adds 30 seconds of retrieval. Both may answer correctly, yet B can finish later. The formula is not end-to-end useful throughput and cannot answer whether memory cost is justified alone.

**Incorrect recall reversal.** A correct recovering system can have RR=0.10; a system that confidently answers incorrectly can have RR=0. The ungated formula rewards B. Correctness is mandatory, and failed trials cannot disappear from summaries.

**Strict-gate collapse.** If every failed retention probe triggers re-supply and any failed first-attempt probe fails eligibility, eligible trials generally have R=0. The candidate index then equals raw TPS for eligible trials. The strict gate is defensible for avoiding wrong-state credit but weak for comparing recovery burden. This blocks adopting the formula as a useful ranking measure without further review. A later alternative could gate final task success and report first-attempt retention separately, but that explicitly permits recovered failures and requires a reviewed interpretation.

**Branch identity conflict.** If A recalls correctly and B needs re-supply, fully identical realized prompts either give A unnecessary help or withhold B's recovery. Freeze identical base prompts and branch policy; allow treatment-dependent paths and report them. “Identical prompts” needs this qualification in the eventual experiment.

**Aggregation mismatch.** Two trials: TPS=10, RR=0 gives eTPS=10; TPS=100, RR=0.9 gives eTPS=10. Median eTPS is 10, whereas median(TPS) × (1−median(RR)) is 55 × 0.55 = 30.25. Compute paired trial values first.

## Small deterministic corpus blueprint (next stage)

Use neutral domains and finite structured answer fields. Planned tasks: retained fact; supersession plus current/historical query; unresolved contradiction; legitimate clarification; new evidence; context pressure; failed recall with recovery; confidently incorrect recall; voluntary recap; expired/out-of-contract state; mixed recovery spans. Include alternate response traces for correct, wrong, unknown, malformed, and timeout outcomes. The same manifest must yield expected R classifications without reading model identity.

For each manifest, manually verify source delivery, both ends of every obligation interval, expected answer, branch selection, recovery span union and denominator accounting. Numeric token goldens wait until a tokenizer is selected. This blueprint is not yet a frozen corpus or an executable test suite.

## Review outcome

Authority, state versioning, finite branching, and token provenance can support mechanical measurement within a restricted corpus. The formula survives only as provisional arithmetic with a narrower possible interpretation. Voluntary recap semantics, strict gating versus recovery usefulness, canonical governance, tokenizer choice, and raw timing availability remain release blockers. No code repair or controlled model experiment should start yet.

## Draft 1 additions: input-side RR edges

These extend the historical draft 0 attacks above. Expected outcomes below use draft 1's proposed scripted recovery policy. They are hand-derived fixtures, not executed tests. Token counts are illustrative accounting fixtures pending selection of a real tokenizer and text-to-token goldens.

| ID | Frozen trace / attack | Expected outcome |
|---|---|---|
| R01 | Entire measured trial has no newly delivered user input; prior context and assistant output exist | I=R=0; RR and eTPS unavailable, not zero. Prior context replay cannot manufacture I. |
| R02 | One turn has no user input, but earlier user events in the same trial contribute I=40 and R=0 | Whole-trial RR=0/40=0; do not confuse a per-turn empty denominator with the trial denominator. |
| R03 | Recovery-branch message has 20 tokens; token indices 0–7 intersect a frozen active-state re-supply span; the remainder adds a new task request | Increment I by 20 and R by 8. The actual trial ratio also includes all earlier user events. |
| R04 | One token intersects both a recovery span and new-content span; two obligations also reference it | Count it once in R and once in I under the frozen intersection convention. |
| R05 | Mixed message lacks a frozen span annotation or references an expired obligation | Missing annotation blocks mechanical fixture eligibility; expired obligation contributes no R. Never classify using a live judgment call. |
| R06 | Fixed voluntary recap adds 20 tokens after a correct probe, with no recovery branch | Increment I by 20, R by 0; record recap assistance. RR may fall through denominator dilution; no improved-memory claim follows. |
| R07 | Model gives a wrong answer; frozen harness delivers a correction without a model request | Active annotated re-supply counts in R. Unprompted correction is not automatically voluntary recap. |
| R08 | Operator recognizes the memory arm and omits a scripted recovery or adds defensive text | Protocol deviation; retain and disclose trace, invalidate controlled comparison under frozen policy. No discretionary relabeling. |
| R09 | Replay identical responses and public state through the branch policy with only arm identity changed | Identical event selection and spans. Arm identity must not influence recovery decisions. |
| R10 | Same text measured with two tokenizers yields (R,I)=(10,100) and (12,80) | RR=0.10 and 0.15 are tokenizer-relative and not comparable as one measurement series. Freeze one tokenizer across arms. |
| R11 | Two counting passes reproduce identical token IDs/offsets and verified subset R | Valid accounting; multiple passes are not a defect. A mismatched representation fails verification even if R≤I numerically. |
| R12 | First user input contributes 100 tokens; recovery adds 100; final output is five tokens | R=100, I=200, RR=0.5 irrespective of the five-token answer. eTPS is 0.5×measured raw TPS when otherwise eligible, not measured useful-output throughput. |
| R13 | One attempt emits 50 tokens in 1 s; retrying trace emits 150 in 3 s; identical newly delivered input and no re-supply | Both raw TPS=50, RR=0 and diagnostic index=50. Attempts and task cost differ; formula is blind to that retry cost. |

Do not infer a high ratio solely from 100 re-supplied tokens: its size depends on complete-trial I. Report R as well as RR. Scheduled recap treatment and corpus text remain authority-sensitive even with automated branching; freezing removes operator discretion, not corpus-author bias.
