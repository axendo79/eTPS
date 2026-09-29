"""Admission safeguards for the offline implementation, not experiment policy."""
from pathlib import Path

# Software safety limits, not benchmark budgets. Valid synthetic fixtures are
# over 100 times smaller; deliberately malformed depth probes are not admitted JSON.
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_PLAN_BYTES = 64 * 1024 * 1024
MAX_EXPORT_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_NODES = 250_000
MAX_PLAN_SLOTS = 100_000
MAX_SCRIPT_RESPONSES = 100_000
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_JSON_NESTING_DEPTH = 1024


def check(value, name):
    from .scorer import InvalidRecord
    if value > globals()[name]:
        raise InvalidRecord(name + ": software safety limit exceeded")


def check_json_depth(raw):
    """Scan structural ASCII bytes before decoding, ignoring quoted escapes."""
    depth, quoted, escaped = 0, False, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            check(depth, "MAX_JSON_NESTING_DEPTH")
        elif byte in (93, 125):
            depth -= 1


def check_value_depth(value):
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list, tuple)):
            depth += 1
            check(depth, "MAX_JSON_NESTING_DEPTH")
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth) for child in children)


def read_file(path, limit):
    """Stat before reading; bounded read also catches growth after the stat."""
    path = Path(path)
    check(path.stat().st_size, limit)
    with path.open("rb") as stream:
        raw = stream.read(globals()[limit] + 1)
    check(len(raw), limit)
    return raw
