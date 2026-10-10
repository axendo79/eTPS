# Review record assembly

Codex-authored maintainer tooling; SYNTHETIC software tests are not human review.
This converts an explicit [review-sheet export](REVIEW_SHEET.md) into the existing
closed corpus-review-v1 declaration without changing freeze admission.

~~~powershell
& $TaskPython -B -m etps_v02.intake.review_record REVIEW_INPUT.json PRIVATE_BUNDLE NEW_REVIEW.json
~~~

API: assemble_review(input_raw, bundle, output) creates an explicitly named new
file **outside** the input bundle with exclusive creation. It never writes into
that bundle, replaces a file, fabricates a reviewer/date, or creates a freeze
receipt. CLI stdout is a canonical JSON status; exit 0 means assembled and
accepted by the existing freeze admission gate in a temporary copy; exit 2
means refusal. semantics_verified remains false.

The export is strict UTF-8 JSON with closed review-input-v1 fields, exactly one
entry per source task, the five exact checklist keys, boolean true for every
check, string notes, nonblank reviewer/date and an explicit empty defects array.
It refuses missing/extra/duplicate tasks, missing/extra checks, false checks,
integer 1 in place of true, malformed/duplicate-key JSON, unknown versions/fields,
or a SHA-256 differing from the bundle's exact source.json bytes. Every listed
defect blocks assembly: no conversion, filtering or defect removal occurs.
If the input bundle already contains review.json, it must have a well-formed
empty defects array; existing defects also block this tool. Preserve prior
findings/resolution evidence through the maintainer's release procedure.

The resulting corpus-review-v1 has the supplied reviewer/date,
obligations_answer_keys_cross_checked=true, the unchanged empty defects array,
and SHA-256 bindings for **every** file other than review.json, including additional
review evidence and evaluation parent receipts. Notes cannot be added to the
closed freeze declaration. Retain the original export in the private bundle
before assembly to bind its complete checklist/notes/defects as evidence. Include
the source, mapper outputs, exact brief, authorship and settings, plus any other
intended frozen artifacts before running; adding one afterward requires assembly
against that revised complete inventory.

The assembler copies the inventory plus candidate review.json to Python's
temporary directory, then calls corpus_freeze.admission on files read from that
copy. This is the same gate create_freeze uses: it re-derives every mapper artifact,
validates sidecars, counts, provenance/settings, dataset separation and complete
review hashes. No provisional freeze time or release name is invented. The
source bundle is re-read before and after exclusive output creation; a detected
change prevents a success result. An interruption or late mutation may leave
an unusable output; preserve the failure and use a new explicit path.

Temporary copies contain all private text and keys. The maintainer must choose
a private temporary directory using TEMP/TMP on Windows (TMPDIR on Unix) under
the same custody restrictions, and keep it outside the bundle. Synthetic local
verification uses only ignored scratch/tmp under this repository.

After inspecting the new record, the human custodian copies its exact bytes as
review.json into a new complete private release bundle (no overwrite of an older
release). Run corpus_freeze create and verify normally with explicit release,
dataset and frozen-at declarations. Adding review.json alone leaves its artifact
bindings correct because the review itself is excluded from that map. Do not add
other files after assembly. The normal freeze/verify checks remain mandatory.

Refusal codes added here include review_input_json, review_input_fields,
review_input_type, review_input_version, source_binding, review_tasks,
review_unchecked, review_defect, output_path, temporary_path, output_exists, output_changed and
bundle_changed. Existing freeze/admission refusal codes propagate unchanged.
This is identity/declared-review enforcement, not independent attestation or
proof of semantics, corpus fairness, author independence or execution.
