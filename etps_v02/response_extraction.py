"""Frozen opt-in byte extraction; original response bytes are never rewritten."""

ASCII_WHITESPACE = b" \t\n\r\v\f"


def fence_v1(raw):
    candidate = raw.strip(ASCII_WHITESPACE)
    lines = candidate.split(b"\n")
    opening = lines[0].removesuffix(b"\r")
    if (len(lines) < 2 or opening.rstrip(b" ") not in (b"```", b"```json")
            or lines[-1] != b"```"):
        return raw, False
    # Another fence line would mean nested/multiple blocks, not one block.
    if any(line.lstrip(b" \t").startswith(b"```") for line in lines[1:-1]):
        return raw, False
    return candidate[candidate.index(b"\n") + 1:-3], True


def project_reply(raw, answer_schema, rule=None):
    from .runner import answer_from_raw
    projected, extracted = fence_v1(raw) if rule == "fence-v1" else (raw, False)
    return answer_from_raw(projected, answer_schema), extracted
