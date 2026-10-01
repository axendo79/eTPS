"""Deterministic synthetic persistence scaling checks."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02 import workload
from etps_v02.persistence import Store
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


if __name__ == "__main__":
    unittest.main()
