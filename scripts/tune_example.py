"""One real local run per invocation; keep every attempt for editorial comparison."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from patchpitch import generator
from patchpitch.models import PitchInput


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--name",required=True)
    parser.add_argument("--case",default="idle-fantasy-shop",choices=["idle-fantasy-shop","pocket-orchard","library-ledger","beautifulrepo"])
    args=parser.parse_args()
    if not args.name.replace("-","").isalnum():raise ValueError("Use a simple attempt name")
    directory=ROOT/"artifacts"/"ifs-comparison"
    directory.mkdir(exist_ok=True)
    target=directory/f"{args.name}.json"
    if target.exists():raise FileExistsError("Keep prior attempts; choose a fresh name")
    data=json.loads((ROOT/"examples"/f"{args.case}.json").read_text(encoding="utf-8"))
    record={"timestamp":datetime.now(timezone.utc).isoformat(),"input":data,"prompt":generator.PROMPT,"schema":generator.PITCH_SCHEMA,"model":generator.MODEL}
    original_transport=generator.ollama_json
    def recorded_transport(*transport_args,**kwargs):
        raw=original_transport(*transport_args,**kwargs)
        record["raw_response"]=raw
        return raw
    generator.ollama_json=recorded_transport
    try:
        request=PitchInput.model_validate(data)
        record["request_payload"]=generator.build_payload(request)
        record["schema"]=record["request_payload"]["format"]
        record["response"]=generator.generate(request)
        record["status"]="EXERCISED"
    except generator.GenerationError as exc:
        record.update(status="FAILED",error=exc.message,code=exc.code)
    target.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(record.get("response",record),indent=2,ensure_ascii=False))


if __name__=="__main__":main()
