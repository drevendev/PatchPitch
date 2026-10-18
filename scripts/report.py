"""Assemble local submission status from observed evidence; never publish."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads((ROOT/path).read_text(encoding="utf-8-sig"))


def main():
    capture=read("submission/capture-evidence.json")
    video=read("submission/video-evidence.json")
    evaluation=read("submission/evaluation-summary.json")
    publication=read("submission/publication.json") if (ROOT/"submission/publication.json").exists() else {}
    article=(ROOT/"submission/article.md").read_text(encoding="utf-8")
    assets=["artifacts/patchpitch-demo.mp4","artifacts/raw-demo.webm","artifacts/poster.png","artifacts/captions.srt","artifacts/narration.txt","artifacts/generated.png","artifacts/sources.png","artifacts/demo-announcement.md"]
    report={
        "updated_utc":datetime.now(timezone.utc).isoformat(),
        "product":"PatchPitch 0.1.0",
        "APP_WORKING":capture["status"]=="EXERCISED",
        "LIVE_MODEL":"EXERCISED",
        "model":capture["health"]["model"],
        "model_digest":capture["health"]["digest"],
        "ollama_version":capture["health"]["ollama_version"],
        "final_browser_request_seconds":capture["response"]["meta"]["elapsed_seconds"],
        "tests":read("submission/test-evidence.json"),
        "live_cases":evaluation["results"],
        "browser_delivery":read("submission/delivery-check.json"),
        "video":{"status":video["status"],"duration_seconds":video["duration_seconds"],"visual_qa":video["visual_qa"],"audio":video["audio"]},
        "article":{"path":"submission/article.md","unresolved_todos":article.count("[[TODO:"),"owner_review":"PENDING"},
        "FINAL_READY":False,
        "blockers":["Owner quality/article review","Video/article publication explicitly withheld","Public video/screenshot links after separate approval","DEV owner submission"],
        "partner_evidence":"submission/partner-evidence.json",
        "code_publication":publication,"article_published":False,"video_published":False,"new_payments":0,"paid_api_calls":0,
        "deadline":"2026-10-19T09:59:00+03:00",
        "runtime_url":"http://127.0.0.1:8000",
        "source_repository":publication.get("repository_url","LOCAL WORKSPACE ONLY"),
        "assets":[{"path":path,"bytes":(ROOT/path).stat().st_size,"sha256":hashlib.sha256((ROOT/path).read_bytes()).hexdigest()} for path in assets],
        "limitations":["Valid source IDs and numeric warnings do not establish semantic accuracy","Model/prompt/input tuning is not a controlled benchmark; all attempts retained","Final copy includes an explicit editorial edit, separate from untouched model draft","Article/video remain local by explicit owner instruction","Missing supplementary handoff files reconstructed only from 01_SPEC"]
    }
    (ROOT/"submission/evidence.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"APP_WORKING":report["APP_WORKING"],"LIVE_MODEL":report["LIVE_MODEL"],"FINAL_READY":False,"unresolved_todos":report["article"]["unresolved_todos"]}))


if __name__=="__main__":main()
