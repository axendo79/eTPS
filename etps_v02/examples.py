"""Run with python -m etps_v02.examples. Synthetic results only."""
import hashlib
import json
from fractions import Fraction

from .scorer import UNIT, OUTCOMES, digest, score


def example(recovery=True, extra_bytes=0, wall=2):
    """900 scheduled ASCII bytes, optional 100-byte authorized recovery."""
    def user(text, target, spans=None):
        return {"kind": "user", "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "spans": spans or [], "failure": "probe", "next": target}
    def probe(good, bad):
        return {"kind": "probe", "expected": {"state": "a"},
                "unknown_answers": [{"status": "unknown"}, {"status": "refusal"}], "obligations": ["state"],
                "next": {k: good if k == "correct" else bad for k in OUTCOMES}}
    manifest = {"unit": UNIT, "start": "intro", "obligations": {
        "state": {"source": "intro", "begin_after": "intro", "end_before": "$trial_end"}}, "nodes": {
        "intro": user("a" * (900 + extra_bytes), "probe"),
        "probe": probe("pass", "recovery"),
        "recovery": user("a" * 100, "retry", [[0, 100, "state"]]),
        "retry": probe("pass", "fail"),
        "pass": {"kind": "terminal", "accepted": True},
        "fail": {"kind": "terminal", "accepted": False}}}
    events = [{"kind": "user", "node": "intro", "text": manifest["nodes"]["intro"]["text"]},
              {"kind": "probe", "node": "probe", "status": "ok",
               "answer": {"state": "wrong" if recovery else "a"},
               "generation": {"tokens": 50, "seconds": 1}}]
    if recovery:
        events += [{"kind": "user", "node": "recovery", "text": "a" * 100},
                   {"kind": "probe", "node": "retry", "status": "ok", "answer": {"state": "a"},
                    "generation": {"tokens": 50, "seconds": 1}}]
    return score(manifest, {"manifest_sha256": digest(manifest), "events": events, "wall_seconds": wall,
                            "purpose": "offline-verification"})


def results():
    return {"evidence": "synthetic replay verification; no model runs",
            "A_recovery": example(),
            "diluted_different_profile_noncomparable": example(extra_bytes=9000),
            "B_no_recovery_with_30s_extra_cost": example(recovery=False, wall=32)}


def serialize(value):
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator,
                "decimal_display": float(value)}
    raise TypeError(type(value).__name__)


if __name__ == "__main__":
    print(json.dumps(results(), default=serialize, indent=2))
