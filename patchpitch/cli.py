"""Non-interactive command line. JSON stdout is separate from stderr progress."""
import argparse
import sys
from pathlib import Path

from .run_store import RunError, write_json


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RunError("ARGUMENT_ERROR", message)


def parser():
    root = Parser(prog="patchpitch")
    commands = root.add_subparsers(dest="command", required=True, parser_class=Parser)
    run = commands.add_parser("run", help="Run a JSON/TOML campaign without a web server")
    run.add_argument("--job", required=True)
    output = run.add_mutually_exclusive_group(required=True)
    output.add_argument("--out")
    output.add_argument("--out-root", help="Choose a stable run directory from the input digest (for schedulers)")
    run.add_argument("--plan", action="store_true")
    for name in ("resume", "validate", "export", "deliver"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--run", required=True)
        if name == "export":
            cmd.add_argument("--kind", choices=["session"], required=True)
            cmd.add_argument("--out", required=True)
        if name == "deliver":
            cmd.add_argument("--channel", choices=["dev"], required=True)
            cmd.add_argument("--mode", choices=["draft"], required=True)
            cmd.add_argument("--target")
            cmd.add_argument("--existing-id", type=int)
    voice = commands.add_parser("voice")
    action = voice.add_subparsers(dest="action", required=True, parser_class=Parser).add_parser("build")
    action.add_argument("--config", required=True)
    action.add_argument("--out", required=True)
    action.add_argument("--language", choices=["en", "ru"], default="ru")
    action.add_argument("--format", choices=["telegram", "x_single", "dev_article", "github_release_notes"], default="telegram")
    schema = commands.add_parser("schema")
    schema.add_argument("--kind", choices=["job", "hashtags", "voice"], default="job")
    schema.add_argument("--out", required=True)
    for cmd in commands.choices.values():
        cmd.add_argument("--json", action="store_true")
    action.add_argument("--json", action="store_true")
    return root


def dispatch(args):
    from . import campaigns
    if args.command == "run":
        return campaigns.run(args.job, args.out, args.plan, args.out_root)
    if args.command == "resume":
        return campaigns.resume(args.run)
    if args.command == "validate":
        from .campaign_export import validate_run
        return validate_run(args.run)
    if args.command == "export":
        from .campaign_export import export_session
        export_session(args.run, args.out)
        return {"status": "exported", "artifacts": {"session": str(Path(args.out).resolve())}}, 0
    if args.command == "schema":
        from .jobs import Job, VoiceConfig
        from .hashtags import Catalog
        model = {"job": Job, "voice": VoiceConfig, "hashtags": Catalog}[args.kind]
        write_json(args.out, model.model_json_schema())
        return {"status": "exported", "artifacts": {"schema": str(Path(args.out).resolve())}}, 0
    if args.command == "voice":
        from .jobs import VoiceConfig, load_config, validate_model
        from .voice import prepare_voice
        config = validate_model(VoiceConfig, load_config(args.config))
        value = prepare_voice(config, Path(args.config).resolve().parent, language=args.language, format=args.format)
        destination = Path(args.out).resolve()
        if destination.exists() and any(destination.iterdir()):
            raise RunError("OUTPUT_NOT_EMPTY", "Select an empty output directory for a voice build.")
        write_json(destination / "voice-bundle.json", value)
        return {"status": "built", "build_id": value["context"]["build_id"],
                "artifacts": {"voice_bundle": str(destination / "voice-bundle.json")}}, 0
    if args.command == "deliver":
        from .publishers.dev import deliver
        return deliver(args.run, args.target, args.existing_id), 0
    raise RunError("ARGUMENT_ERROR", "Unknown command.")


def main(argv=None):
    import json
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        result, code = dispatch(parser().parse_args(argv))
    except RunError as exc:
        result, code = {"schema_version": "patchpitch.summary/v1", "run_id": None, "status": "failed",
                        "targets": {}, "artifacts": {}, "errors": [exc.as_dict()], "warnings": []}, exc.exit_code
    except KeyboardInterrupt:
        result, code = {"status": "interrupted", "errors": [{"code": "INTERRUPTED", "message": "Use resume to continue saved work."}]}, 130
    except OSError:
        result, code = {"status": "failed", "errors": [{"code": "FILESYSTEM_ERROR", "message": "Cannot read or write a required campaign file."}]}, 2
    except Exception as exc:
        from .generator import GenerationError
        if isinstance(exc, GenerationError):
            result, code = {"status": "failed", "errors": [{"code": exc.code, "message": exc.message}]}, 3 if exc.status in {409, 503} else 4
        else:
            print("Internal failure: " + type(exc).__name__, file=sys.stderr)
            result, code = {"status": "failed", "errors": [{"code": "INTERNAL_ERROR", "message": "An internal error stopped the command. Saved checkpoints remain available."}]}, 4
    result = {"schema_version": "patchpitch.summary/v1", "run_id": None, "targets": {}, "artifacts": {},
              "errors": [], "warnings": [], **result}
    if "--json" in argv:
        # A single, Unicode-safe document even in Windows legacy code pages.
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    else:
        print(result["status"])
        for error in result.get("errors", []):
            print(error["code"] + ": " + error["message"], file=sys.stderr)
        for name, path in result.get("artifacts", {}).items():
            print(f"{name}: {path}")
    return code
