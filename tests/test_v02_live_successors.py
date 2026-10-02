"""Live import guard with historical replay compatibility."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.live_runner import run_live
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode, sha, validate_bundle
from test_v02_field_routing import fields_manifest
from test_v02_live_adapter import FakeServer, bundle, manifest
from test_v02_runner import bundle as offline_bundle


class LiveSuccessorTests(unittest.TestCase):
    def live_bundle(self, task, endpoint="http://127.0.0.1"):
        plan, _ = bundle(endpoint)
        raw = encode(task)
        plan["tasks"] = {"synthetic-task": sha(raw)}
        return encode(plan), {sha(raw): raw}

    def test_timeout_probe_allowed_other_outcomes_rejected(self):
        for outcome in ("timeout", "correct", "incorrect", "unknown", "malformed"):
            task = manifest()
            task["nodes"]["p2"] = copy.deepcopy(task["nodes"]["p"])
            task["nodes"]["p"]["next"][outcome] = "p2"
            with self.subTest(outcome=outcome):
                if outcome == "timeout":
                    validate_bundle(*self.live_bundle(task))
                else:
                    with self.assertRaisesRegex(InvalidRecord, "live probe successor"):
                        validate_bundle(*self.live_bundle(task))

    def test_field_route_probe_rejected(self):
        task = fields_manifest()
        task["nodes"]["p"]["field_routes"][0]["next"] = "retry"
        del task["nodes"]["r-a"]
        with self.assertRaisesRegex(InvalidRecord, "live probe successor"):
            validate_bundle(*self.live_bundle(task))

    def test_user_and_terminal_successors_allowed(self):
        validate_bundle(*self.live_bundle(manifest()))
        validate_bundle(*self.live_bundle(fields_manifest()))

    def test_offline_probe_successor_still_imports(self):
        task = manifest()
        task["nodes"]["p2"] = copy.deepcopy(task["nodes"]["p"])
        task["nodes"]["p"]["next"]["correct"] = "p2"
        validate_bundle(*offline_bundle(manifest=task))

    def test_old_journal_replays_without_import_gate(self):
        task = manifest()
        task["nodes"]["p2"] = copy.deepcopy(task["nodes"]["p"])
        task["nodes"]["p"]["next"]["incorrect"] = "p2"
        with tempfile.TemporaryDirectory() as temp, FakeServer() as server:
            with patch("etps_v02.live_plan.check_live_successors"):
                store = Store.create(Path(temp) / "old.db", *self.live_bundle(task, server.url))
                try:
                    result = run_live(store, "slot", allow_live=True)
                    exported = export_bundle(store, format="v2")
                finally:
                    store.close()
            self.assertEqual(replay_export(exported)["trials"][0], result)
