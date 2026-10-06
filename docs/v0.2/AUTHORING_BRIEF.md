# Conversation authoring brief

Version: `authoring-brief-v1`. Output format: `authoring-v1`.

Write realistic fictional conversations in which facts change, lapse, disagree,
and are asked about later. Use ordinary language and ordinary situations.
Questions concern conversation order, including earlier checkpoints, rather
than external calendar dates. Write tasks and answers from the conversation's
stated facts alone. Do not design them around a particular answering method.

Each task has exactly one primary family. Cover all nine:

| Family | Structure and questions |
|---|---|
| F1 | Long update chain: one property changes several times; ask its present value. |
| F2 | Checkpoint history: several changes; ask the value at a named earlier point, including after a later lapse. |
| F3 | Change then lapse: changes end in an explicit lapse without a successor; balance with still-active, reinstated, and never-established cases. |
| F4 | Disagreement: equally authoritative sources disagree; balance unresolved cases with explicitly stated precedence, sometimes stated only later. |
| F5 | Similar entities: naturally similar names and properties change independently; ask about one entity. No spelling tricks. |
| F6 | Distance and pressure: separate facts and questions with irrelevant material that makes no claims about the facts being tested. Include conversations within and beyond the declared context budget. |
| F7 | Mixed question: ask current and historical values, and applicable status, together in separate answer fields. |
| F8 | Provenance: ask which public source or message established the present value. Every answering condition receives the same public identifiers. |
| F9 | Controls: single unchanged fact, never-established fact, legitimate clarification, and explicit expiration without an update chain. |

Distribute partial-property changes, scoped exceptions, negation/retraction, and
reinstatement after a lapse across families. For compound facts, change only the
stated component; for an exception, preserve other scopes. Include A→B→A revisits
as well as chains with distinct successive values. Reinstatement is a new
version even when the value repeats. Explicit precedence must resolve a
disagreement; mere recency does not. Preserve the earlier unresolved checkpoint.

Use matched question wording across active, expired, reinstated, and
never-established cases, and across resolved and unresolved disagreements.
Use unpredictable fictional values rather than familiar names, stereotyped
answers, or round numbers. Include some cases where exact earlier passages
suffice to answer. Keep family names, coverage tags, predictions, answer keys,
and outcome labels out of the conversation and questions sent for answering.
Public message identifiers are permitted and required. Mark any scheduled recap
in the authoring data; it is still part of the scheduled conversation.

Answers are strict JSON objects with exact field names and exact scalar values
(string, integer, or null). No approximate matching, spelling normalization,
booleans, floating-point numbers, nested objects, or prose answers. Designated
set fields are arrays of those scalars: the complete unordered set is required;
missing, extra, or duplicate elements fail. Separate disagreement status and
competing values into different fields. Give each field exactly one dimension:
`current`, `historical`, `expired`, `ambiguity`, `provenance`, or `control`.
Each field is one unit, including a whole set. Freeze one logical `field_map`
per task; each question uses an unchanged subset. An omitted field remains
unavailable; never rename or redefine it. First-answer and final-answer counts
are separate; partial field credit does not change task acceptance.

Choose chain-length ranges, distractor volume, counts, and the context budget
on a separately identified development set. Then write and freeze an untouched
evaluation set: aim for at least six tasks in each of F1–F8 and at least four
F9 controls, roughly fifty tasks. These are coverage targets, not statistical
precision claims. Record exact final counts and pressure settings. Do not revise,
drop, or replace evaluation tasks based on answering outcomes. Freeze predictions
before any evaluation execution; predictions never select tasks for inclusion.

For every task, record structural separation predictions with reasons. Use
anonymous condition IDs A–F: A receives the complete earlier conversation;
B receives only the question; C receives isolated earlier factual statements;
D receives exact earlier conversation passages; E and F are two additional
conditions whose behavior is unspecified here. Predict failure only from the
task's structure and the stated information available. Use null when a condition
cannot be predicted from that information, with a reason. Include every condition
once and summarize predictions by family. Never assume a question-only answer
must fail: measure successful guessing separately.

Write UTF-8 JSON by hand using this complete format. All listed fields are
required; objects are closed. Empty arrays and nulls are explicit. Arrays for
conversation and versions are ordered; other collections representing sets
have unique members. IDs are nonempty strings, unique across message, question,
and correction IDs. Do not use IDs beginning with `$` or containing `:`.

- Root: `version` = `authoring-v1`, `brief_version` = `authoring-brief-v1`,
  `dataset` = `development` or `evaluation`, and `tasks` (nonempty array).
- Task: `id`, `family` (F1–F9), `coverage_tags`, `conversation`, `field_map`,
  `probes`, `state_history`, `recoveries`, `predictions`.
- `coverage_tags`: `chain_depth` and `distance` (nonnegative integers),
  `entity_similarity` (`distinct`/`similar`), `ambiguity_status`
  (`active`/`expired`/`unestablished`/`unresolved`/`resolved`),
  `provenance_need` (`needed`/`none`), `context_pressure` (`within`/`over`),
  `verbatim_possible` (boolean), and `subcases` (unique array from
  `partial`, `scoped`, `negation`, `retraction`, `reinstatement`, `revisit`).
- Conversation message: `id`, `text`, `recap` (boolean). Text starts with
  `[id] ` using its actual ID, followed by the exact public message. Include
  the response instructions in public text: strict JSON and the requested
  field names. Conversation order is delivery order.
- Root task `field_map`: field name to an object with `dimension`, `record`
  (proposition ID), `kind` (`current`/`at-checkpoint`/`status`/`values`/
  `provenance`/`clarification`), `checkpoint` (message ID for at-checkpoint,
  null otherwise). At-checkpoint means the state just after that message.
- Question (`probes` entry): `id`, `position` (message or correction ID after
  which it is asked), `wording` (starts with `[id] `), `field_map` (an exact
  subset of the task map), `expected` (one JSON object), `set_fields` (unique
  field names), `unknown_answers` (exact admitted unknown-answer objects),
  `alternative_answers` (other desired correct objects), `requirements`
  (unique IDs tested), and `outcomes`. Expected keys equal this question's
  map; `values` queries require set designation. Unknown and correct answers
  must not overlap, including a reordered set. Alternative correct forms and
  clarification queries can be recorded, but may require a format expansion
  before execution; do not substitute another answer silently.
- `outcomes`: exactly `correct`, `incorrect`, `unknown`, `malformed`, `timeout`.
  Correct uses `$continue`; each other outcome uses `$reject` or a correction
  ID. `$continue` resumes the ordered schedule (or ends in acceptance after
  its last question); `$reject` ends in failure. No implicit retry count.
- Proposition (`state_history` entry): `id`, `entity`, `property`, `scope`,
  `status_labels` (exact strings for `active`, `expired`, `unresolved`,
  `unestablished`), and ordered `versions`. Separate records for distinct
  properties and scopes. An empty version list represents never-established.
- Version: `id`, `message` (establishing event ID), `change`
  (`establish`/`change`/`lapse`/`reinstate`/`precedence`), `status`
  (`active`/`expired`/`unresolved`), `value`, `sources`, `time`, `applicability`,
  and `requirements`. The message identifies establishment, change, lapse,
  reinstatement, or precedence explicitly; versions progress in message order.
- Source: `message`, `authority` (plain description), `value`. Active state
  has one matching source/value; unresolved state has distinct source messages
  and null single value; expired state has null value and no sources.
  Precedence selects a previously recorded claim. Preserve all earlier versions.
- `time`: `begin`, `end` (plain world-validity labels or null); they are distinct
  from message order. `applicability` is a plain nonempty scope description.
- Requirement: `id`, `kind` (`current`/`historical`), `begin_after`, `end_before`.
  Current requirements end at the next version's message or `$trial_end`.
  Historical requirements have independently declared ends. Explicitly record
  starts and ends; a delayed start may be unexecutable and must be reported.
  Reinstatement requires fresh IDs. Tested requirements must be active at the
  question and any correction that repeats their facts.
- Correction (`recoveries` entry): `id`, `failure_probes` (question IDs), `text`
  (starts with `[id] `), `spans` (arrays `[begin,end,requirement_id]` for repeated
  facts), `new_spans` (arrays `[begin,end]` for new content), `retry` (question ID).
  Use half-open UTF-8 byte offsets at character boundaries; never edit text to
  fit offsets. The retry's position is this correction ID. Freeze exact text
  and outcome routes in advance, one correction per declared route. Multiple
  originating questions may be unexecutable and must be reported.
- Prediction: `arm` (A–F), `failing` (boolean or null), `reason` (nonempty plain
  explanation). These records are private authoring data, never public messages.

Supply all branches, answers, annotations, and predictions before freezing.
Keep the original bytes unchanged. A format check cannot establish whether
the conversation truly supports the answers: have a separate reviewer cross-check
the complete history, sources, requirements, and keys. Any mismatch blocks release.
