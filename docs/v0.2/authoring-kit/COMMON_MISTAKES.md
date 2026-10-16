# Common authoring mistakes

Generic repairs for the answer-form, wording, ID and typing issues described in
the public [brief](../AUTHORING_BRIEF_V2.md), [answer contract](../ANSWER_CONTRACT.md),
[lint guide](../AUTHORING_LINT.md) and [runbook](../AUTHORING_RUNBOOK.md). This is
not a fresh inspection of development rounds or evaluation content. Every example
below is SYNTHETIC; no private task, answer, ID or finding was consulted.

| Mistake | Synthetic illustration and repair |
| --- | --- |
| Vague numeric form | “Give the tray count” leaves `"61"`, `61.0` and `"61 trays"` unspecified. Declare a JSON integer: `{"count":61}`. Existing frozen d10/fence policies remain separate from preferred wording. |
| Loose text copying | If the conversation says `navli-7`, `"the navli-7"` or `"Navli-7"` fails. Require exact text, including case, punctuation and spacing. |
| Wrapped or descriptive IDs | `"[SYNTHETIC-x-m001]"` and `"message SYNTHETIC-x-m001"` fail. Return `"SYNTHETIC-x-m001"` as a JSON string, with an explicit null condition or prohibition. Numeric-looking identifiers stay strings. |
| Wrong source after precedence | A later decision selects the earlier claim. The source field names that earlier public claim, not the decision message. All arms must see the same IDs. |
| Null surrogate | `"null"`, `""`, `[]`, unknown and refusal cannot replace scalar JSON `null`. For opted-in scalars, use null exactly when expired, unestablished or unresolved. Active literal-null facts are excluded. |
| Scalar/set confusion | Current scalar is null during unresolved conflict; the current set contains every competing value. After settlement the set is a singleton. After lapse/absence it is `[]`, never `[null]`. No duplicates or superseded values. |
| Historical set | “Which labels competed then?” has no historical-set representation. Use scalar at-checkpoint fields; do not mislabel an earlier set as values in force now. |
| Misnamed status | After explicit settlement/reinstatement use `active`, never `resolved`. Ordinary status wording must list all four exact labels, even when the expected one seems obvious. Recency alone cannot settle equal-authority claims. |
| Missing versus expired | A withdrawn permit was supplied earlier; it is expired, not missing_information. Designated missing status applies only to an actually required item never supplied before that question. Declare its own proposition, including an empty version list. |
| Unnamed missing item | “Ask for the missing detail” is open ended. State the exact required-item ID in the question; status is exactly missing_information and any identifier field returns that same declared proposition ID. Ordinary absence is unestablished. |
| Ordinary and missing labels mixed | Do not offer active/unresolved alternatives in a designated missing-status clause. Keep separate questions/projections, as in F9. The identifier projection asks for an ID, not a status word. |
| Terse retry | “Try again with the same fields” lacks the field forms. Every retry gets its own full H3 question, exact fields, types, null conditions and status vocabulary. |
| One field borrowing another's rules | A null clause for `source` does not define the null rule for `earlier`. Render every applicable field slot; review each field independently. |
| Wrong correction prefix | `<task>-r001` is a requirement, not a correction. Corrections use **`<task>-c001`**, not `-recovery`, `-c01` or `-c000`. All six categories use the literal task prefix and 001–999. |
| Reference/prefix drift | Renaming a message without updating its `[id] ` public prefix, checkpoint/source references and requirement boundaries fails. Keep all links byte-exact. A new naming convention never rewrites a frozen release. |
| Annotation language in messages | “This expires here” or “new active version” reveals annotations. Use ordinary events such as “Cancel the cabinet token without issuing another.” Keep family/coverage/prediction/key labels out of messages. |
| Answer too close to question | With a question after m006, m004–m006 are the three-message window. A source at m006 still violates the rule; put three unrelated messages after the last tested evidence. Correction text is exempt, other nearby messages are not. |
| Filler cues the task | “For the next question, remember…” is prohibited even without the value. Irrelevant material must make no claims about tested facts or upcoming questions. |
| Character-based evidence position | With 11 conversation messages, only messages 1–2 are in the first tenth. Making message 1 long does not move message 3 into that window. Review tested transitions, sources and obligation evidence; absence has no positive source location. |
| Guessing pressure from characters | Long text is not proof of token overflow. Measure with the declared counter. Over requires ≥1.5× budget; within requires <0.5×. Record actual message/character/token sizes, full-request headroom and the 2048-token reply reserve. |
| Late or stale obligations | Start at establishment, not a later convenient message. End a current requirement at the next version; use separately declared historical requirements for earlier checkpoints. Reinstatement gets fresh IDs. |
| Invalid recovery linkage | One correction cannot combine two failed questions or repeat an inactive obligation. Freeze its single failure link, route, UTF-8 spans and retry; never adapt a recap to treatment identity. |
| Treating software success as review | Lint exit 0 can include warnings. Admission/intake/conformance/freeze cannot prove the conversation supports the key, absence is truthful, sizes were measured, or review was independent. Every unresolved defect blocks release. |

For a mechanical refusal, keep the original unchanged and inspect the upstream
diagnostic **privately**. Record the defect and its resolution in a new revision;
do not silently edit frozen artifacts or use outcomes to select evaluation tasks.
Only the kit's complete summary line is intended for sharing with an agent.
