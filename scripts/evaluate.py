"""Explicit six-call experiment: baseline and app prompt, same model and inputs."""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from patchpitch.generator import MODEL, OPTIONS, GenerationError, model_input, ollama_json
from patchpitch.models import PitchInput


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Make six real local inference requests")
    args=parser.parse_args()
    if not args.live:
        print("NOT_RUN. Use --live after starting Ollama and PatchPitch on 127.0.0.1:8000.")
        return
    output=ROOT / "artifacts" / "evaluation"
    output.mkdir(parents=True, exist_ok=True)
    results=[]
    for name in ["beautifulrepo", "pocket-orchard", "library-ledger"]:
        data=json.loads((ROOT/"examples"/f"{name}.json").read_text(encoding="utf-8"))
        request=PitchInput.model_validate(data)
        for variant in ["baseline", "structured"]:
            record={"case":name,"kind":"LIVE_MODEL","variant":variant,"model":MODEL,"options":OPTIONS,"timestamp":datetime.now(timezone.utc).isoformat(),"input":data,"human_review":{"status":"OWNER_REVIEW_PENDING","incorrect_additions":None,"missing_main_points":None,"clarity":None,"editing_seconds":None,"notes":None}}
            start=time.perf_counter()
            try:
                if variant == "baseline":
                    payload={"model":MODEL,"stream":False,"messages":[{"role":"user","content":"Write short release notes for this product and audience, using these changes.\n"+json.dumps(model_input(request))}],"options":OPTIONS,"keep_alive":"10m"}
                    response=ollama_json("/api/chat",payload,timeout=180)
                else:
                    http=urllib.request.Request("http://127.0.0.1:8000/api/pitch",data=json.dumps(data).encode(),headers={"Content-Type":"application/json"})
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(http,timeout=200) as r:
                        response=json.load(r)
                record.update(status="EXERCISED",response=response)
                record["output_sha256"]=hashlib.sha256(json.dumps(response,sort_keys=True).encode()).hexdigest()
            except (GenerationError,urllib.error.URLError,TimeoutError,ValueError) as exc:
                record.update(status="FAILED",error=str(exc))
                if isinstance(exc,urllib.error.HTTPError): record["error_response"]=exc.read().decode(errors="replace")
            record["elapsed_seconds"]=round(time.perf_counter()-start,3)
            record["input_sha256"]=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
            results.append(record)
            (output/f"{name}-{variant}.json").write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding="utf-8")
            print(f"{name} {variant}: {record['status']} {record['elapsed_seconds']}s",flush=True)
    (ROOT/"submission"/"evaluation-summary.json").write_text(json.dumps({"kind":"LIVE_MODEL","results":[{k:r[k] for k in ["case","variant","status","elapsed_seconds"]} for r in results],"owner_quality_review":"PENDING","claims":"No winner or quality improvement claimed"},indent=2),encoding="utf-8")


if __name__ == "__main__": main()
