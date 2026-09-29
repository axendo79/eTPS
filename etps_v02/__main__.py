"""Offline-only CLI. No endpoint, API key, network client, or model loader."""
import argparse
import json
import sys
from pathlib import Path

from .persistence import Store
from .runner import export_bundle, json_default, replay_export, report, run_offline
from .workload import decode, sha
from .scorer import InvalidRecord
from .limits import read_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    exported = commands.add_parser("replay-export")
    exported.add_argument("file")
    exported.add_argument("--validate-authoring", action="store_true",
                          help="Reassert the current authoring gate in addition to replay integrity checks")
    create = commands.add_parser("import")
    create.add_argument("database")
    create.add_argument("--plan", required=True)
    create.add_argument("--artifact", action="append", required=True)
    for name in ("run", "report", "export", "abort"):
        command = commands.add_parser(name)
        command.add_argument("database")
        if name in {"run", "abort"}:
            command.add_argument("--slot", required=True)
        if name == "abort":
            command.add_argument("--code", required=True)
            command.add_argument("--reason", default="")
        if name == "export":
            command.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "replay-export":
        result = replay_export(decode(read_file(args.file, "MAX_EXPORT_BYTES")),
                               validate_authoring=args.validate_authoring)
        print(json.dumps(result, default=json_default, ensure_ascii=False, indent=2))
        return
    if args.command == "import":
        artifacts = {}
        for name in args.artifact:
            raw = read_file(name, "MAX_ARTIFACT_BYTES")
            artifacts[sha(raw)] = raw
        store = Store.create(args.database, read_file(args.plan, "MAX_PLAN_BYTES"), artifacts)
    else:
        store = Store(args.database)
    try:
        if args.command == "run":
            result = run_offline(store, args.slot)
        elif args.command == "abort":
            store.abort(args.slot, args.code, args.reason)
            result = report(store)
        elif args.command == "export":
            result = export_bundle(store)
            with Path(args.output).open("x", encoding="utf-8") as output:
                json.dump(result, output, default=json_default, ensure_ascii=False, indent=2)
            result = {"output": args.output, "purpose": "offline-verification"}
        else:
            result = report(store)
        print(json.dumps(result, default=json_default, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        main()
    except InvalidRecord as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
