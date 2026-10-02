"""Re-chained missing-field evidence raises InvalidRecord, never KeyError."""
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from etps_v02.boundary_delivery import Path as DeliveryPath
from etps_v02.live_runner import run_live
from etps_v02.manual_runner import run_manual
from etps_v02.persistence import Store
from etps_v02.runner import export_bundle, replay_export
from etps_v02.scorer import InvalidRecord
from etps_v02.workload import encode
from test_v02_boundary_delivery import plan as delivery_plan
from test_v02_live_adapter import FakeServer, bundle, manifest
from test_v02_manual_dev import manual_bundle, paste
from test_v02_session_profile import rechain


class ReplayFieldsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.count = 0

    def create(self, plan, artifacts):
        self.count += 1
        store = Store.create(Path(self.temp.name) / f"{self.count}.db", encode(plan), artifacts)
        self.addCleanup(store.close)
        return store

    def assert_missing_fields(self, exported, index, fields):
        for field in fields:
            with self.subTest(index=index, field=field):
                damaged = copy.deepcopy(exported)
                del damaged["journal"]["slot"][index]["payload"][field]
                rechain(damaged)
                with self.assertRaises(InvalidRecord):
                    replay_export(damaged)

    def test_live_http_probe_and_delivery_fields(self):
        for provider in ("openai-compatible", "anthropic"):
            for delivery in (False, True):
                with self.subTest(provider=provider, delivery=delivery), FakeServer(provider) as server:
                    plan, artifacts = delivery_plan(server.url) if delivery else bundle(server.url, provider)
                    arm = plan["arms"]["private-arm-label"]
                    arm["provider"] = provider
                    if provider == "anthropic":
                        arm["anthropic_version"] = "2023-06-01"
                    store = self.create(plan, artifacts)
                    run_live(store, "slot", allow_live=True)
                    exported = export_bundle(store)
                self.assertTrue(replay_export(exported)["trials"][0]["evidence_verified"])
                for index, row in enumerate(exported["journal"]["slot"]):
                    if row["kind"] == "request":
                        fields = ["node", "elapsed_seconds", "deadline_seconds", "body"]
                        if row["payload"].get("kind") == "delivery":
                            fields.append("kind")
                    elif row["kind"] == "event":
                        fields = ["kind", "node"]
                        if row["payload"]["kind"] == "user":
                            fields += ["text"]
                        elif row["payload"]["kind"] in {"probe", "delivery"}:
                            fields += ["raw_base64", "client_latency_seconds", "http_body_base64",
                                       "http_body_sha256", "http_status", "status", "usage", "generation",
                                       "generation_source", "backend_stats", "transport_detail"]
                            if row["payload"]["kind"] == "probe":
                                fields += ["answer"]
                    else:
                        continue
                    self.assert_missing_fields(exported, index, fields)

    def test_live_transport_failure_fields(self):
        for delivery in (False, True):
            with FakeServer() as server:
                plan, artifacts = delivery_plan(server.url) if delivery else bundle(server.url)
                store = self.create(plan, artifacts)
                with patch("etps_v02.adapter_openai._http_once", return_value=(None, None, "transport_error")):
                    run_live(store, "slot", allow_live=True)
                exported = export_bundle(store)
            self.assertTrue(replay_export(exported)["trials"][0]["evidence_verified"])
            for index, row in enumerate(exported["journal"]["slot"]):
                if row["kind"] == "event" and row["payload"]["kind"] in {"probe", "delivery"}:
                    self.assertIsNone(row["payload"]["http_body_base64"])
                    fields = ["kind", "node", "raw_base64", "client_latency_seconds", "http_body_base64",
                              "status", "usage", "generation", "generation_source", "backend_stats", "transport_detail"]
                    if row["payload"]["kind"] == "probe":
                        fields.append("answer")
                    self.assert_missing_fields(exported, index, fields)

    def test_manual_probe_fields(self):
        store = self.create(*manual_bundle())
        run_manual(store, "slot", allow_manual=True, stdin=io.BytesIO(paste()), stdout=io.StringIO())
        exported = export_bundle(store)
        index = next(i for i, row in enumerate(exported["journal"]["slot"])
                     if row["kind"] == "event" and row["payload"]["kind"] == "probe")
        self.assert_missing_fields(exported, index, ["raw_base64", "coded_raw_base64", "status", "answer"])

    def test_delivery_path_subscripts_and_optional_request_kind(self):
        task = manifest()
        path = DeliveryPath(task)
        with self.assertRaises(InvalidRecord):
            path.request({})
        for payload in ({"kind": "user"}, {"node": "intro"}):
            with self.subTest(payload=payload), self.assertRaises(InvalidRecord):
                path.event(payload)
        path.event({"kind": "user", "node": "intro", "text": task["nodes"]["intro"]["text"]})
        path.request({"node": "p"})  # Probe kind was and remains optional.
