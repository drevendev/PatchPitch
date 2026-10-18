"""Opt-in comparison. Matching configuration is not a quality benchmark."""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from patchpitch import generator
from patchpitch.models import PitchInput

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def app_json(path, data=None):
    request = urllib.request.Request("http://127.0.0.1:8000" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type":"application/json"})
    with OPENER.open(request, timeout=generator.TIMEOUT + 15) as response:
        return json.load(response)


def model_key(name):
    return name if ":" in name else name + ":latest"


def preflight():
    """Refuse a mismatch before requesting inference."""
    health = app_json("/api/health")
    tags = generator.ollama_json("/api/tags").get("models", [])
    local = next((m for m in tags if model_key(m["name"]) == model_key(generator.MODEL)), None)
    if health.get("ollama") != "ready" or not local:
        raise ValueError("Model unavailable; no comparison inference was requested.")
    if (model_key(health.get("model", "")) != model_key(generator.MODEL)
            or health.get("options") != generator.OPTIONS
            or not local.get("digest") or health.get("digest") != local["digest"]):
        raise ValueError("App and evaluator model/digest/options differ; no comparison inference was requested.")
    return {"app_health":health,"local_model":local,"requested_options":dict(generator.OPTIONS)}


def response_identity(response, variant, before, after):
    meta = response if variant == "baseline" else response.get("meta", {})
    actual = meta.get("model")
    # Ollama does not echo sampling options. Keep its exact request as evidence.
    options = dict(generator.OPTIONS) if variant == "baseline" else meta.get("options")
    comparable = bool(actual and model_key(actual) == model_key(before["local_model"]["name"])
                      and options == before["requested_options"] and before == after)
    return {"model_reported_by_response":actual,"options":options,
            "options_evidence":"exact Ollama request" if variant == "baseline" else "app response metadata",
            "digest_before":before["local_model"]["digest"],"digest_after":after["local_model"]["digest"],
            "configuration_comparable":comparable}


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Make six local inference requests after configuration preflight")
    args = parser.parse_args()
    if not args.live:
        print("NOT_RUN. Use --live with matching app/evaluator settings. No inference requested.")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = ROOT / "artifacts" / "evaluation" / stamp
    output.mkdir(parents=True)
    summary = {"kind":"LIVE_MODEL","status":"NOT_RUN","attempt":stamp,"results":[],
               "owner_quality_review":"PENDING","claims":"No controlled benchmark, winner or quality improvement claimed"}
    try:
        before = preflight()
        summary["preflight"] = before
        for name in ["beautifulrepo", "pocket-orchard", "library-ledger"]:
            data = json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))
            request = PitchInput.model_validate(data)
            for variant in ["baseline", "structured"]:
                record = {"case":name,"kind":"LIVE_MODEL","variant":variant,"timestamp":datetime.now(timezone.utc).isoformat(),
                          "input":data,"input_sha256":hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),
                          "human_review":{"status":"OWNER_REVIEW_PENDING","incorrect_additions":None,"missing_main_points":None,"clarity":None}}
                start = time.perf_counter()
                try:
                    if preflight() != before:
                        raise ValueError("Configuration changed; this pair is non-comparable.")
                    if variant == "baseline":
                        payload = {"model":generator.MODEL,"stream":False,"messages":[{"role":"user","content":"Write short release notes for this product and audience, using these changes.\n" + json.dumps(generator.model_input(request))}],"options":generator.OPTIONS,"keep_alive":"10m"}
                        if generator.MODEL.startswith("gemma4"):
                            payload["think"] = True
                        record["request_payload"] = payload
                        response = generator.ollama_json("/api/chat", payload, timeout=generator.TIMEOUT)
                    else:
                        record["app_request"] = data
                        response = app_json("/api/pitch", data)
                    record["response"] = response
                    record["identity"] = response_identity(response, variant, before, preflight())
                    record["output_sha256"] = hashlib.sha256(json.dumps(response,sort_keys=True).encode()).hexdigest()
                    complete = bool(response.get("done") and response.get("done_reason") != "length") if variant == "baseline" else "draft" in response
                    record["status"] = "EXERCISED" if record["identity"]["configuration_comparable"] and complete else "NON_COMPARABLE"
                except (generator.GenerationError, OSError, ValueError) as exc:
                    record.update(status="FAILED",error=str(exc))
                    if isinstance(exc, urllib.error.HTTPError):
                        record["error_response"] = exc.read().decode(errors="replace")
                record["elapsed_seconds"] = round(time.perf_counter() - start, 3)
                (output / f"{name}-{variant}.json").write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding="utf-8")
                summary["results"].append({k:record[k] for k in ["case","variant","status","elapsed_seconds"]})
                print(f"{name} {variant}: {record['status']} {record['elapsed_seconds']}s",flush=True)
        summary["status"] = "EXERCISED" if all(r["status"] == "EXERCISED" for r in summary["results"]) else "NON_COMPARABLE"
    except (generator.GenerationError, OSError, ValueError) as exc:
        summary.update(status="PREFLIGHT_FAILED",error=str(exc))
    finally:
        serialized = json.dumps(summary,indent=2,ensure_ascii=False)
        (output / "summary.json").write_text(serialized,encoding="utf-8")
        (ROOT / "submission" / "evaluation-summary.json").write_text(serialized,encoding="utf-8")
        print(json.dumps({"status":summary["status"],"attempt":stamp}))


if __name__ == "__main__":
    main()
