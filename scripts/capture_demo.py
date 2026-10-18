"""Record one real UI → local Gemma → edit → export flow. No network mocking."""
import hashlib
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools"/"browsers"))
from playwright.sync_api import sync_playwright


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    parser=argparse.ArgumentParser()
    parser.add_argument("--edit-file",type=Path,help="Explicit local editorial text; never substitutes for the model response")
    args=parser.parse_args()
    artifacts=ROOT/"artifacts"
    raw_dir=artifacts/"raw"
    raw_dir.mkdir(parents=True,exist_ok=True)
    provenance=json.loads((ROOT/"examples/idle-fantasy-shop.provenance.json").read_text(encoding="utf-8"))
    evidence={"kind":"LIVE_MODEL","status":"NOT_RUN","timestamp":datetime.now(timezone.utc).isoformat(),"input_kind":"Technical notes from the actual Idle Fantasy Shop 0.11.1 to 0.12 code patch","patch_provenance":provenance,"devlog_used_as_input":False,"mock_transport":False,"timeline":{}}
    context=None
    video=None
    start=time.perf_counter()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            start=time.perf_counter()
            def mark(name): evidence["timeline"][name]=round(time.perf_counter()-start,3)
            try:
                context=browser.new_context(viewport={"width":1920,"height":1080},record_video_dir=str(raw_dir),record_video_size={"width":1920,"height":1080},device_scale_factor=1,permissions=["clipboard-read","clipboard-write"])
                page=context.new_page()
                video=page.video
                page.goto("http://127.0.0.1:8000",wait_until="networkidle")
                health=page.request.get("http://127.0.0.1:8000/api/health").json()
                evidence["health"]=health
                if health["ollama"] != "ready": raise RuntimeError("Local model not ready; no replacement output will be recorded")
                expected_prompt=hashlib.sha256((ROOT/"patchpitch/prompts/release.txt").read_text(encoding="utf-8").encode()).hexdigest()
                if health.get("prompt_sha256") != expected_prompt: raise RuntimeError("Restart the local server: its loaded prompt does not match the current file")
                page.wait_for_timeout(2000)
                page.screenshot(path=str(artifacts/"empty.png"))
                mark("example")
                page.get_by_role("button",name="Try an example").click()
                page.locator("#selection-panel > summary").click()
                page.get_by_role("checkbox",name="Include C09").wait_for()
                page.wait_for_timeout(1800)
                # Show an explicit exclusion; the marker already excluded it by default.
                page.get_by_role("checkbox",name="Include C09").check()
                page.wait_for_timeout(600)
                page.get_by_role("checkbox",name="Include C09").uncheck()
                page.locator("#selection-panel > summary").click()
                page.get_by_label("I confirm the selected changes").check()
                page.wait_for_timeout(1500)
                page.screenshot(path=str(artifacts/"input.png"))
                mark("generate")
                with page.expect_response(lambda r:r.url.endswith("/api/pitch") and r.request.method=="POST",timeout=610000) as response_info:
                    page.get_by_role("button",name="Write the announcement").click()
                response=response_info.value
                evidence["input"]=response.request.post_data_json
                evidence["response"]=response.json()
                evidence["http_status"]=response.status
                if response.status != 200: raise RuntimeError(str(evidence["response"]))
                page.locator("#result").wait_for(state="visible")
                mark("result")
                page.wait_for_timeout(3500)
                page.screenshot(path=str(artifacts/"generated.png"))
                mark("sources")
                page.locator("#sources > summary").click()
                page.locator("#source-list details").first.locator("summary").click()
                page.wait_for_timeout(2000)
                # Full-page capture temporarily resizes Chromium's recording surface.
                # Keep the recorded viewport fixed; it otherwise produces gray frames.
                page.screenshot(path=str(artifacts/"sources.png"))
                page.locator("#sources > summary").click()
                mark("edit")
                original=evidence["response"]["markdown"]
                edited=original
                if args.edit_file:
                    page.get_by_role("button",name="Edit draft",exact=True).click()
                    edited=args.edit_file.read_text(encoding="utf-8")
                    page.locator("#editor").fill(edited)
                    page.locator("#editor").evaluate("el => { el.scrollTop=0; el.setSelectionRange(0,0); }")
                else:
                    # Review additional changes without touching the generated words.
                    page.locator(".more-changes > summary").click()
                page.wait_for_timeout(3000)
                page.get_by_role("button",name="Copy Markdown",exact=True).click()
                assert page.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n") == edited
                mark("download")
                with page.expect_download() as download_info:
                    page.get_by_role("button",name="Download Markdown").click()
                destination=artifacts/"demo-announcement.md"
                download_info.value.save_as(str(destination))
                assert destination.read_text(encoding="utf-8") == edited
                page.wait_for_timeout(2500)
                page.screenshot(path=str(artifacts/"edited.png"))
                evidence.update(status="EXERCISED",input_sha256=digest(evidence["input"]),output_sha256=digest(evidence["response"]),export_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),manual_edit={"performed":bool(args.edit_file),"kind":"Explicit editorial edit" if args.edit_file else "No editorial edits; untouched model Markdown exported","original_markdown":original,"edited_markdown":edited,"original_title":original.splitlines()[0],"edited_title":edited.splitlines()[0]},clipboard_matches_export=True)
                mark("end")
            except Exception as exc:
                evidence.update(status="FAILED",error=str(exc))
                if context: context.pages[0].screenshot(path=str(artifacts/"capture-failure.png"))
            finally:
                if context: context.close()
                if video:
                    shutil.copyfile(video.path(),artifacts/"raw-demo.webm")
                    evidence["raw_video"]="artifacts/raw-demo.webm"
                    evidence["raw_sha256"]=hashlib.sha256((artifacts/"raw-demo.webm").read_bytes()).hexdigest()
                browser.close()
    except Exception as exc:
        evidence.update(status="FAILED",error=str(exc))
    serialized=json.dumps(evidence,indent=2,ensure_ascii=False)
    (ROOT/"submission"/"capture-evidence.json").write_text(serialized,encoding="utf-8")
    (artifacts/f"capture-{int(start)}-{uuid4().hex[:8]}.json").write_text(serialized,encoding="utf-8")
    print(json.dumps({"status":evidence["status"],"timeline":evidence["timeline"],"error":evidence.get("error")}))
    if evidence["status"] != "EXERCISED": sys.exit(1)


if __name__ == "__main__": main()
