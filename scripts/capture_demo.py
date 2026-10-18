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

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools"/"browsers"))
from playwright.sync_api import sync_playwright


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--edit-file",type=Path,help="Explicit local editorial text; never substitutes for the model response")
    args=parser.parse_args()
    artifacts=ROOT/"artifacts"
    raw_dir=artifacts/"raw"
    raw_dir.mkdir(parents=True,exist_ok=True)
    evidence={"kind":"LIVE_MODEL","status":"NOT_RUN","timestamp":datetime.now(timezone.utc).isoformat(),"input_kind":"Real Idle Fantasy Shop 0.12 update; selected facts from published devlog","source_url":"https://drevengames.itch.io/idle-fantasy-shop/devlog/1714671/title-012-plan-a-little-let-the-fields-rest","mock_transport":False,"timeline":{}}
    context=None
    video=None
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
            page.wait_for_timeout(2000)
            page.screenshot(path=str(artifacts/"empty.png"))
            mark("example")
            page.get_by_role("button",name="Try an example").click()
            page.get_by_role("checkbox",name="Include C05").wait_for()
            page.wait_for_timeout(1800)
            # Show an explicit exclusion; the marker already excluded it by default.
            page.get_by_role("checkbox",name="Include C05").check()
            page.wait_for_timeout(600)
            page.get_by_role("checkbox",name="Include C05").uncheck()
            page.get_by_label("I confirm the selected changes").check()
            page.wait_for_timeout(1500)
            page.screenshot(path=str(artifacts/"input.png"))
            mark("generate")
            with page.expect_response(lambda r:r.url.endswith("/api/pitch") and r.request.method=="POST",timeout=210000) as response_info:
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
            page.locator("#sources summary").click()
            page.wait_for_timeout(2000)
            page.screenshot(path=str(artifacts/"sources.png"),full_page=True)
            page.locator("#sources summary").click()
            mark("edit")
            page.get_by_role("button",name="Edit draft",exact=True).click()
            original=page.locator("#editor").input_value()
            lines=original.splitlines()
            # Real editorial change remains explicit, separate from model output.
            lines[0]="# Plan your crafting. Give the fields a rest."
            edited=args.edit_file.read_text(encoding="utf-8") if args.edit_file else "\n".join(lines)+"\n"
            page.locator("#editor").fill(edited)
            page.locator("#editor").evaluate("el => { el.scrollTop=0; el.setSelectionRange(0,0); }")
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
            evidence.update(status="EXERCISED",input_sha256=digest(evidence["input"]),output_sha256=digest(evidence["response"]),export_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),manual_edit={"kind":"Explicit scripted editorial edit, separate from untouched model output; owner quality review pending","original_markdown":original,"edited_markdown":edited,"original_title":original.splitlines()[0],"edited_title":edited.splitlines()[0]},clipboard_matches_export=True)
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
    serialized=json.dumps(evidence,indent=2,ensure_ascii=False)
    (ROOT/"submission"/"capture-evidence.json").write_text(serialized,encoding="utf-8")
    (artifacts/f"capture-{int(start)}.json").write_text(serialized,encoding="utf-8")
    print(json.dumps({"status":evidence["status"],"timeline":evidence["timeline"],"error":evidence.get("error")}))
    if evidence["status"] != "EXERCISED": sys.exit(1)


if __name__ == "__main__": main()
