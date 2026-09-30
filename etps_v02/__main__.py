"""Offline by default; live plans require explicit dispatch authorization."""
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
    models = commands.add_parser("check-models")
    models.add_argument("plan")
    models.add_argument("--allow-remote", action="store_true")
    exported = commands.add_parser("replay-export")
    exported.add_argument("file")
    exported.add_argument("--validate-authoring", action="store_true",
                          help="Reassert the current authoring gate in addition to replay integrity checks")
    create = commands.add_parser("import")
    create.add_argument("database")
    create.add_argument("--plan", required=True)
    create.add_argument("--artifact", action="append", required=True)
    create.add_argument("--allow-remote", action="store_true")
    for name in ("run", "report", "export", "abort"):
        command = commands.add_parser(name)
        command.add_argument("database")
        if name in {"run", "abort"}:
            command.add_argument("--slot", required=True)
        if name == "run":
            command.add_argument("--allow-manual", action="store_true")
            command.add_argument("--reply-sentinel", default="<<<END_ETPS_REPLY>>>")
            command.add_argument("--allow-live", action="store_true")
            command.add_argument("--allow-remote", action="store_true")
        if name == "abort":
            command.add_argument("--code", required=True)
            command.add_argument("--reason", default="")
        if name == "export":
            command.add_argument("--audience", choices=("evidence", "leaderboard", "website"), default="evidence")
            command.add_argument("--output", required=True)
            command.add_argument("--format", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()
    if args.command == "check-models":
        from .model_check import check_models
        results = check_models(decode(read_file(args.plan, "MAX_PLAN_BYTES")), allow_remote=args.allow_remote)
        for result in results:
            print(result["arm"] + ": " + result["status"])
        if any(result["status"] != "ok" for result in results):
            raise InvalidRecord("model checks failed; metadata lookup does not prove generation compatibility")
        return
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
        store = Store.create(args.database, read_file(args.plan, "MAX_PLAN_BYTES"), artifacts,
                             allow_remote=args.allow_remote)
    else:
        store = Store(args.database)
    try:
        if args.command == "run":
            if store.plan["schema"] == "etps-manual-plan-v1":
                from .manual_runner import run_manual
                result = run_manual(store, args.slot, allow_manual=args.allow_manual, sentinel=args.reply_sentinel)
            elif store.plan["schema"] == "etps-live-plan-v1":
                from .live_runner import run_live
                result = run_live(store, args.slot, allow_live=args.allow_live, allow_remote=args.allow_remote)
            else:
                result = run_offline(store, args.slot)
        elif args.command == "abort":
            store.abort(args.slot, args.code, args.reason)
            result = report(store)
        elif args.command == "export":
            result = export_bundle(store, format=args.format, audience=args.audience)
            with Path(args.output).open("x", encoding="utf-8") as output:
                json.dump(result, output, default=json_default, ensure_ascii=False, indent=2)
            result = {"output": args.output, "purpose": store.plan["purpose"]}
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
