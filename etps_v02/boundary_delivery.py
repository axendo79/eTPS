"""Deliver-v1 path validation and separate processing observations."""
from .scorer import classify_probe, mapping, require, route


class Path:
    def __init__(self, manifest):
        self.manifest = manifest
        self.current = manifest["start"]
        self.dirty = False
        self.delivered = False

    def request(self, request):
        mapping(request, "journal.request", ("node",))
        node = self.manifest["nodes"][self.current]
        kind = "delivery" if node["kind"] == "session_boundary" else "probe"
        require(request["node"] == self.current and request.get("kind", "probe") == kind,
                "delivery request path mismatch")
        require(node["kind"] == "probe" or (node["kind"] == "session_boundary" and self.dirty
                and not self.delivered), "unexpected delivery request")

    def event(self, event):
        mapping(event, "journal.event", ("node", "kind"))
        node = self.manifest["nodes"][self.current]
        kind = event["kind"]
        require(event["node"] == self.current, "delivery event path mismatch")
        if kind == "delivery":
            require(node["kind"] == "session_boundary" and self.dirty and not self.delivered,
                    "unexpected delivery event")
            self.dirty, self.delivered = False, True
            return
        require(kind == node["kind"], "delivery event kind mismatch")
        if kind == "session_boundary":
            require(not self.dirty, "missing boundary delivery")
            self.delivered = False
        elif kind == "user":
            self.dirty = True
        elif kind == "probe":
            self.dirty = False
            self.current, _ = route(self.manifest, node, event, classify_probe(self.manifest, node, event))
            return
        self.current = node["next"]


def scoring_events(manifest, events):
    path = Path(manifest)
    for event in events:
        path.event(event)
    return [event for event in events if event["kind"] != "delivery"]


def observations(rows, provider):
    from .timing import project
    result, pending = [], None
    for row in rows:
        p = row["payload"]
        if row["kind"] == "request" and p.get("kind") == "delivery":
            pending = {"node": p["node"], "status": "unanswered", "generation": None,
                       "generation_source": None, "timing": None, "usage": None}
            result.append(pending)
        elif row["kind"] == "event" and p["kind"] == "delivery" and pending is not None:
            pending.update(status=p["status"], generation=p.get("generation"),
                           generation_source=p.get("generation_source"), usage=p.get("usage"),
                           timing=project(provider, p))
            pending = None
    return result
