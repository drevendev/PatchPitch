"""Opt-in Sentry evidence: offline privacy audit or one real public model call.

Outputs are private local evidence, not files to commit or publish automatically.
The controlled invalid fixture is human-written; it never creates an LLM span.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import HttpTransport, Transport
from patchpitch import generator, telemetry
from patchpitch.models import PitchInput


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_check(output, *, live=False, dsn_file=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {"kind": "LIVE_SENTRY_CHECK" if live else "OFFLINE_PRIVACY_AUDIT",
              "started_utc": datetime.now(timezone.utc).isoformat(), "status": "FAILED",
              "live_model": "NOT_RUN", "delivery": "NOT_ATTEMPTED", "http": []}
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
        report.update(commit=sha, working_tree_dirty=dirty)
        os.environ["PATCHPITCH_SENTRY_RELEASE"] = sha
        dsn = (Path(dsn_file).read_text(encoding="utf-8").strip() if dsn_file
               else os.getenv("PATCHPITCH_SENTRY_DSN", "")) if live else "https://offline@example.invalid/1"
        if not dsn:
            report["failure"] = "missing_explicit_dsn"
            return report
        packets = []

        class OfflineTransport(Transport):
            def capture_envelope(self, envelope):
                body = envelope.serialize()
                packets.append(body)
                (output / f"envelope-{len(packets):02}.txt").write_bytes(body)

        class AuditedHttpTransport(HttpTransport):
            # This is the actual HTTP body at the pinned SDK's network boundary.
            # Never record the destination, DSN or authentication headers.
            def _request(self, method, endpoint_type, body, headers):
                encoding = headers.get("Content-Encoding", headers.get("content-encoding", ""))
                decoded = gzip.decompress(body) if encoding == "gzip" else body
                if encoding not in {"", "gzip"}:
                    raise ValueError("Unsupported audit encoding")
                packets.append(decoded)
                index = len(packets)
                (output / f"envelope-{index:02}.txt").write_bytes(decoded)
                receipt = {"packet": index, "sha256": hashlib.sha256(body).hexdigest(),
                           "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
                           "encoding": encoding, "status": None}
                report["http"].append(receipt)
                response = super()._request(method, endpoint_type, body, headers)
                receipt["status"] = response.status
                return response

        if not telemetry.configure(dsn=dsn, transport_type=AuditedHttpTransport if live else OfflineTransport):
            report["failure"] = "sdk_initialization_failed"
            return report
        request_data = json.loads((ROOT / "examples/pocket-orchard.json").read_text(encoding="utf-8"))
        request = PitchInput.model_validate(request_data)
        write_json(output / "input.json", request_data)
        if live:
            report["live_model"] = "ATTEMPTED_ONCE"
            try:
                result = generator.generate(request)
                write_json(output / "response.json", result)
                (output / "announcement.md").write_text(result["markdown"], encoding="utf-8")
                report["live_model"] = "SUCCEEDED"
                report["success_trace_id"] = result["meta"].get("sentry_trace_id")
            except generator.GenerationError as exc:
                report["failure"] = exc.code
                return report

        fixture = json.loads((ROOT / "examples/sentry-controlled-invalid.json").read_text(encoding="utf-8"))
        write_json(output / "controlled-invalid.json", fixture)
        raw = {"done": True, "message": {"content": json.dumps(fixture)}}
        canary = "PRIVATE_AUDIT_CANARY_NEVER_SEND"
        with sentry_sdk.isolation_scope() as scope:
            # Inject only for the offline audit. No private user data is needed.
            if not live:
                scope.set_user({"email": canary})
                scope.set_extra("changelog", canary)
                scope.set_context("private", {"voice": canary})
                scope.add_breadcrumb({"message": canary})
            with telemetry.generation("devlog", "CONTROLLED_FAILURE") as run:
                try:
                    with run.span("validation") as span:
                        if not live:
                            span.span.set_data("gen_ai.input.messages", canary)
                            span.span.set_data("gen_ai.output.messages", canary)
                        generator.validate_response(raw, request, generator.build_payload(request))
                except generator.GenerationError as exc:
                    run.error(exc.code)
                    report.update(controlled_error_code=exc.code, controlled_trace_id=run.trace_id,
                                  controlled_event_id=run.event_id)
                else:
                    raise AssertionError("Controlled fixture unexpectedly passed")
        telemetry.flush(timeout=15 if live else 2)
        if not packets:
            raise AssertionError("No actual transport packet captured")
        events = [item.payload.json for body in packets for item in Envelope.deserialize(body).items]
        serialized = b"\n".join(packets)
        prohibited = [canary, request.product.name, request.product.description,
                      *[c.text for c in request.changes], fixture["intro"]["text"]]
        if live:
            prohibited.extend(block["text"] for block in [result["raw_draft"]["title"], result["raw_draft"]["intro"],
                                                        *result["raw_draft"]["highlights"]])
        assert all(value.encode() not in serialized for value in prohibited)
        assert all(not {"user", "request", "extra", "breadcrumbs", "exception", "modules", "server_name"} & event.keys()
                   for event in events)
        controlled = next(event for event in events if event.get("transaction") == "patchpitch.controlled_failure")
        assert [s["op"] for s in controlled["spans"]] == ["validation"]
        report["privacy_audit"] = "PASSED_ACTUAL_TRANSPORT_PAYLOAD"
        if live:
            tx = next(event for event in events if event.get("transaction") == "patchpitch.generate")
            def millis(span):
                stamp = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
                return round((stamp(span["timestamp"]) - stamp(span["start_timestamp"])) * 1000, 3)
            report["observation"] = {"total_ms": tx["contexts"]["trace"]["data"]["patchpitch.duration_ms"],
                "spans": [{"op": span["op"], "duration_ms": millis(span), "data": span.get("data", {})} for span in tx["spans"]]}
            report["delivery"] = "HTTP_ACCEPTED" if report["http"] and all(r["status"] == 200 for r in report["http"]) else "NOT_CONFIRMED"
            if report["delivery"] != "HTTP_ACCEPTED":
                report["failure"] = "delivery_not_confirmed"
                return report
        else:
            report["delivery"] = "OFFLINE_NO_NETWORK"
        report["status"] = "PASSED"
        return report
    except Exception as exc:
        # Exceptions can contain credentials/paths: retain only their type.
        report["failure"] = type(exc).__name__
        return report
    finally:
        telemetry.flush(timeout=15 if live else 2)
        telemetry.shutdown()
        write_json(output / "report.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--output", required=True, type=Path, help="Fresh private evidence directory")
    parser.add_argument("--dsn-file", type=Path, help="Local ignored DSN file; live mode only")
    args = parser.parse_args()
    if args.dsn_file and not args.live:
        parser.error("--dsn-file requires --live")
    try:
        report = run_check(args.output, live=args.live, dsn_file=args.dsn_file)
    except FileExistsError:
        parser.error("Output directory already exists; retain it and choose a fresh directory")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
