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
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    parser=argparse.ArgumentParser()
    parser.add_argument("--name",required=True)
    parser.add_argument("--case",default="idle-fantasy-shop",choices=["idle-fantasy-shop","pocket-orchard","library-ledger","beautifulrepo"])
    parser.add_argument("--input",type=Path,help="Explicit local input JSON instead of the example")
    parser.add_argument("--prompt-file",type=Path,help="Explicit local prompt for a controlled comparison")
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--thinking",choices=["on","off"],help="Explicit single-run Gemma thinking comparison")
    args=parser.parse_args()
    if not args.name.replace("-","").isalnum():raise ValueError("Use a simple attempt name")
    directory=ROOT/"artifacts"/"ifs-comparison"
    directory.mkdir(parents=True, exist_ok=True)
    target=directory/f"{args.name}.json"
    if target.exists():raise FileExistsError("Keep prior attempts; choose a fresh name")
    data=json.loads((args.input or ROOT/"examples"/f"{args.case}.json").read_text(encoding="utf-8"))
    if args.prompt_file:
        generator.PROMPT_FILE=args.prompt_file
        generator.POST_PROMPT_FILE=args.prompt_file
    generator.OPTIONS={**generator.OPTIONS,"seed":args.seed}
    if args.thinking:
        normal_builder=generator.build_payload
        def explicit_thinking(*builder_args,**kwargs):
            payload=normal_builder(*builder_args,**kwargs)
            payload["think"]=args.thinking=="on"
            return payload
        generator.build_payload=explicit_thinking
    record={"timestamp":datetime.now(timezone.utc).isoformat(),"input":data,"prompt":generator.read_prompt(data.get("format","devlog")),"schema":generator.PITCH_SCHEMA,"model":generator.MODEL}
    input_path=args.input or ROOT/"examples"/f"{args.case}.json"
    provenance_path=input_path.with_suffix(".provenance.json")
    if provenance_path.exists():
        record["input_provenance"]=json.loads(provenance_path.read_text(encoding="utf-8"))
    original_transport=generator.ollama_json
    def recorded_transport(*transport_args,**kwargs):
        raw=original_transport(*transport_args,**kwargs)
        record["raw_response"]=raw
        return raw
    generator.ollama_json=recorded_transport
    try:
        version=generator.ollama_json("/api/version")
        tags=generator.ollama_json("/api/tags")
        record["runtime"]={"ollama_version":version.get("version"),"model":next((m for m in tags.get("models",[]) if m.get("name")==generator.MODEL),None)}
        request=PitchInput.model_validate(data)
        record["request_payload"]=generator.build_payload(request)
        record["schema"]=record["request_payload"]["format"]
        record["response"]=generator.generate(request)
        record["status"]="EXERCISED"
    except generator.GenerationError as exc:
        record.update(status="FAILED",error=exc.message,code=exc.code)
    target.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding="utf-8")
    if record["status"] == "EXERCISED":
        target.with_suffix(".md").write_text(record["response"]["markdown"],encoding="utf-8")
    if record["status"] == "EXERCISED":
        print(json.dumps({"file":str(target),"status":record["status"],"markdown":record["response"]["markdown"],"warnings":record["response"]["warnings"],"meta":record["response"]["meta"]},indent=2,ensure_ascii=False))
    else:
        print(json.dumps({"file":str(target),"status":record["status"],"code":record.get("code"),"error":record.get("error")},indent=2,ensure_ascii=False))


if __name__=="__main__":main()
