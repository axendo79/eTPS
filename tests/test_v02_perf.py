"""Deterministic synthetic persistence scaling checks."""
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from etps_v02 import workload
from etps_v02.persistence import Store
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import decode, encode, sha
from test_v02_runner import bundle, response


class PerfTests(unittest.TestCase):
    def test_plan_hash_and_head_seeds(self):
        raw, artifacts = bundle(slots=50)
        with tempfile.TemporaryDirectory() as temp:
            with patch("etps_v02.persistence.sha", wraps=sha) as hashed:
                store = Store.create(Path(temp) / "plan.db", raw, artifacts)
            self.addCleanup(store.close)
            self.assertLessEqual(sum(call.args == (raw,) for call in hashed.call_args_list), 2)
            for head in store.db.execute("SELECT * FROM heads"):
                self.assertEqual(head["hash"], sha(encode([sha(raw), head["slot"]])))
                self.assertEqual((head["count"], head["state"]), (0, "unattempted"))
            store.close()

    def test_distinct_scripts_validated_once_per_bundle(self):
        raw, artifacts = bundle(slots=30)
        plan = decode(raw)
        script = encode({"responses": [response()]})
        artifacts[sha(script)] = script
        for slot in plan["slots"][::2]:
            slot["script_sha256"] = sha(script)
        for authoring in (True, False):
            with patch("etps_v02.workload.script_responses", wraps=workload.script_responses) as checked:
                workload.validate_bundle(encode(plan), artifacts, authoring=authoring)
                self.assertEqual(checked.call_count, 2)

    def test_order_matches_full_scan_on_40_seeded_sequences(self):
        rng = random.Random(20261001)
        with tempfile.TemporaryDirectory() as temp:
            for sequence in range(40):
                slots = rng.randint(2, 9)
                raw, artifacts = bundle(slots=slots)
                store = Store.create(Path(temp) / f"order-{sequence}.db", raw, artifacts)
                try:
                    actions = [(rng.randrange(slots), rng.choice(("start", "finish", "abort")))
                               for _ in range(50)]
                    for index in range(slots):
                        actions.extend([(index, "start"), (index, rng.choice(("finish", "abort")))])
                    for ordinal, kind in actions:
                        slot = f"slot-{ordinal}"
                        count, state = store.db.execute(
                            "SELECT count,state FROM heads WHERE slot=?", (slot,)).fetchone()
                        prior = store.db.execute(
                            "SELECT h.state FROM heads h JOIN slots s ON h.slot=s.id WHERE s.ordinal<?",
                            (ordinal,)).fetchall()
                        expected = ("slot already attempted; no implicit rerun" if count else
                                    "planned run order violated" if any(r[0] not in {"finished", "aborted"}
                                                                          for r in prior) else None) if kind == "start" else (
                                    "slot is not running or journal kind is invalid" if state != "running" else None)
                        payload = {"reason_code": "operator_abort"} if kind == "abort" else {}
                        try:
                            store.append(slot, kind, payload)
                            actual = None
                        except InvalidRecord as exc:
                            actual = str(exc)
                        self.assertEqual(actual, expected, (sequence, ordinal, kind))
                finally:
                    store.close()

    def test_start_vm_steps_are_constant(self):
        counts = []
        with tempfile.TemporaryDirectory() as temp:
            for predecessors in (50, 200):
                raw, artifacts = bundle(slots=predecessors + 1)
                store = Store.create(Path(temp) / f"vm-{predecessors}.db", raw, artifacts)
                try:
                    for index in range(predecessors):
                        store.append(f"slot-{index}", "start", {})
                        store.abort(f"slot-{index}", "operator_abort")
                    steps = []
                    store.db.set_progress_handler(lambda: steps.append(1), 1)
                    store.append(f"slot-{predecessors}", "start", {})
                    store.db.set_progress_handler(None, 1)
                    counts.append(len(steps))
                finally:
                    store.close()
        self.assertLess(counts[1] / counts[0], 1.25)


if __name__ == "__main__":
    unittest.main()
