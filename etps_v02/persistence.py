"""Separate SQLite journal for offline v0.2 verification. No legacy DB migration."""
from pathlib import Path
import sqlite3

from .scorer import require
from .workload import decode, encode, sha, validate_bundle

APP_ID = 0x45545032
SCHEMA = 1


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True)
        self.db.row_factory = sqlite3.Row
        try:
            require(self.db.execute("PRAGMA application_id").fetchone()[0] == APP_ID,
                    "not an eTPS offline database")
            require(self.db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA,
                    "unsupported offline schema")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA synchronous=FULL")
            rows = self.db.execute("SELECT raw, hash FROM plan").fetchall()
            require(len(rows) == 1 and sha(rows[0]["raw"]) == rows[0]["hash"], "invalid plan record")
            self.plan_raw = bytes(rows[0]["raw"])
            self.plan_hash = rows[0]["hash"]
            artifacts = {r["hash"]: bytes(r["raw"]) for r in self.db.execute("SELECT hash,raw FROM artifacts")}
            self.plan = validate_bundle(self.plan_raw, artifacts, allow_legacy=True, authoring=False)
            self.artifacts = artifacts
            self.slots = {s["id"]: s for s in self.plan["slots"]}
            actual = [(r["id"], r["ordinal"]) for r in self.db.execute("SELECT id,ordinal FROM slots ORDER BY ordinal")]
            require(actual == [(s["id"], i) for i, s in enumerate(self.plan["slots"])], "slot ledger mismatch")
            require(self.db.execute("SELECT count(*) FROM heads").fetchone()[0] == len(actual),
                    "missing slot heads")
            for slot in self.slots:
                self.entries(slot)
        except BaseException:
            self.db.close()
            raise

    @classmethod
    def create(cls, path, plan_raw, artifacts):
        plan = validate_bundle(plan_raw, artifacts)
        path = Path(path)
        # Refuse any existing path, including a legacy or empty database.
        with path.open("xb"):
            pass
        db = sqlite3.connect(path)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.executescript(f"""
                PRAGMA application_id={APP_ID};
                PRAGMA user_version={SCHEMA};
                CREATE TABLE plan (id INTEGER PRIMARY KEY CHECK(id=1), raw BLOB NOT NULL, hash TEXT NOT NULL);
                CREATE TABLE artifacts (hash TEXT PRIMARY KEY, raw BLOB NOT NULL);
                CREATE TABLE slots (id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE);
                CREATE TABLE heads (slot TEXT PRIMARY KEY REFERENCES slots(id), count INTEGER NOT NULL,
                                    hash TEXT NOT NULL, state TEXT NOT NULL);
                CREATE TABLE journal (slot TEXT NOT NULL REFERENCES slots(id), seq INTEGER NOT NULL,
                                      kind TEXT NOT NULL, payload BLOB NOT NULL, prev TEXT NOT NULL,
                                      hash TEXT NOT NULL, PRIMARY KEY(slot,seq));
            """)
            with db:
                db.execute("INSERT INTO plan VALUES (1,?,?)", (plan_raw, sha(plan_raw)))
                db.executemany("INSERT INTO artifacts VALUES (?,?)", artifacts.items())
                for i, slot in enumerate(plan["slots"]):
                    db.execute("INSERT INTO slots VALUES (?,?)", (slot["id"], i))
                    seed = sha(encode([sha(plan_raw), slot["id"]]))
                    db.execute("INSERT INTO heads VALUES (?,0,?,'unattempted')", (slot["id"], seed))
            for table in ("plan", "artifacts", "slots", "journal"):
                for action in ("UPDATE", "DELETE"):
                    db.execute(f"CREATE TRIGGER immutable_{table}_{action} BEFORE {action} ON {table} "
                               "BEGIN SELECT RAISE(ABORT,'immutable record'); END")
            db.commit()
        finally:
            db.close()
        return cls(path)

    def close(self):
        self.db.close()

    def entries(self, slot):
        require(slot in self.slots, "unknown planned slot")
        previous = sha(encode([self.plan_hash, slot]))
        state = "unattempted"
        result = []
        for i, row in enumerate(self.db.execute("SELECT * FROM journal WHERE slot=? ORDER BY seq", (slot,))):
            payload = bytes(row["payload"])
            expected = sha(encode([slot, i, row["kind"], previous]) + payload)
            require(row["seq"] == i and row["prev"] == previous and row["hash"] == expected,
                    "journal integrity failure")
            kind = row["kind"]
            require((i == 0 and kind == "start") or
                    (state == "running" and kind in {"request", "event", "finish", "abort"}),
                    "invalid journal lifecycle")
            state = {"start": "running", "finish": "finished", "abort": "aborted"}.get(kind, state)
            result.append({"kind": kind, "payload": decode(payload), "sha256": expected})
            previous = expected
        head = self.db.execute("SELECT * FROM heads WHERE slot=?", (slot,)).fetchone()
        require(head is not None and (head["count"], head["hash"], head["state"]) ==
                (len(result), previous, state), "journal head mismatch")
        return result

    def append(self, slot, kind, payload):
        if kind == "abort" and self.plan["schema"] == "etps-offline-plan-v2":
            require(self.plan["invalidation_policy"].get(payload.get("reason_code")) == "invalidate",
                    "abort code must be predeclared invalidation")
        raw = encode(payload)  # Serialize before acquiring write lock or mutating.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            entries = self.entries(slot)
            head = self.db.execute("SELECT * FROM heads WHERE slot=?", (slot,)).fetchone()
            if kind == "start":
                require(not entries, "slot already attempted; no implicit rerun")
                ordinal = self.db.execute("SELECT ordinal FROM slots WHERE id=?", (slot,)).fetchone()[0]
                prior = self.db.execute("SELECT h.state FROM heads h JOIN slots s ON h.slot=s.id WHERE s.ordinal<?",
                                        (ordinal,)).fetchall()
                require(all(r[0] in {"finished", "aborted"} for r in prior), "planned run order violated")
            else:
                require(head["state"] == "running" and kind in {"request", "event", "finish", "abort"},
                        "slot is not running or journal kind is invalid")
            seq, previous = head["count"], head["hash"]
            value = sha(encode([slot, seq, kind, previous]) + raw)
            self.db.execute("INSERT INTO journal VALUES (?,?,?,?,?,?)", (slot, seq, kind, raw, previous, value))
            state = {"start": "running", "finish": "finished", "abort": "aborted"}.get(kind, "running")
            self.db.execute("UPDATE heads SET count=?,hash=?,state=? WHERE slot=?", (seq + 1, value, state, slot))

    def abort(self, slot, code, detail=""):
        from .workload import INVALIDATION_POLICY
        policy = self.plan.get("invalidation_policy", INVALIDATION_POLICY)
        require(policy.get(code) == "invalidate", "abort code must be predeclared invalidation")
        self.append(slot, "abort", {"reason_code": code, "reason": detail})

    def manifest(self, slot):
        require(slot in self.slots, "unknown planned slot")
        key = self.plan["tasks"][self.slots[slot]["task"]]
        return decode(self.artifacts[key])
