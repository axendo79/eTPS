# Disposition: reproduced contract mismatch; compatibility not selected

The six-case proof demonstrates that composite bridge-v2 telemetry is not
compatible with the accepted flat telemetry projection. It does not demonstrate
a projector implementation defect: the independent contract review confirmed
that [LIVE_ADAPTER.md:365](../../../docs/v0.2/LIVE_ADAPTER.md#L365)
explicitly rejects nested and boolean values, and
[STATUS.md:271](../../../docs/STATUS.md#L271)
preserves that rule after the null-handling fix. See the [independent authority checklist](CONTRACT_AUTHORITY_CHECKLIST.md)
for the accepted rules and unresolved mapping decisions.

No compatibility patch is supplied as an authorized fix. The accepted rules
support raw evidence retention, failed/unavailable request denominators,
independent metric coverage and null incomplete totals. They do not select a
mapping from the composite bridge receipt into the current per-request scalar
schema. In particular, an aggregate `ingestions` list is not authority to
invent extraction cost attribution or recover missing usage. The chosen
mapping and replay/version treatment must be reviewed before implementation.

PR35's RUN_RECORD_TELEMETRY_DRAFT is explicitly unaccepted. Its proposed nested
hardware sidecar does not change the current `x_nyx_bridge` projection contract.
Neither scorer acceptance nor first-attempt retention changes are needed to
preserve the demonstrated evidence. Existing bridge fixes remain unapplied.

For any later selected compatibility design, retain these acceptance checks:
known costs on the original failed request remain counted; a cached retry's
zero denotes zero new extraction; both attempt events remain; null unknown
usage never becomes zero; invalid/missing/unavailable coverage remains explicit;
raw evidence survives projection; and old recorded revisions remain replayable.
The prototype's author/system affiliation must stay disclosed, with no
favorable treatment of Nyx failures.
