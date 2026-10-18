"""Review/export the saved REAL Gemma take in the polished UI. No new inference.
The browser response is replayed explicitly; never present this as a live model call.
"""
import hashlib,json,os,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools/browsers"))
from playwright.sync_api import sync_playwright


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    capture=json.loads((ROOT/"submission/capture-evidence.json").read_text(encoding="utf-8"))
    assert capture["status"]=="EXERCISED" and not capture["manual_edit"]["performed"]
    response=capture["response"];timeline={};start=time.perf_counter()
    def mark(name):timeline[name]=round(time.perf_counter()-start,3)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={"width":1920,"height":1080},record_video_dir=str(ROOT/"artifacts/review-raw"),record_video_size={"width":1920,"height":1080},permissions=["clipboard-read","clipboard-write"])
        page=context.new_page();video=page.video
        page.route("**/api/pitch",lambda route:route.fulfill(json=response))
        page.goto("http://127.0.0.1:8000",wait_until="networkidle")
        page.get_by_role("button",name="Try an example").click()
        page.get_by_label("I confirm the selected changes").check()
        page.get_by_role("button",name="Write the announcement").click()
        page.locator("#result").wait_for(state="visible");page.wait_for_timeout(600)
        page.locator("#sources > summary").click();page.wait_for_timeout(350)
        first=page.locator("#source-list details").first
        first.locator("summary").click();page.wait_for_timeout(350)
        first.evaluate("el => el.scrollIntoView({block:'center',behavior:'smooth'})")
        page.wait_for_timeout(700);mark("sources")
        page.screenshot(path=str(ROOT/"artifacts/review-sources.png"))
        page.wait_for_timeout(2500)
        page.locator("#sources > summary").click();page.wait_for_timeout(350)
        page.evaluate("window.scrollTo({top:0,behavior:'instant'})");page.wait_for_timeout(350)
        mark("export")
        page.get_by_role("button",name="Copy Markdown",exact=True).click()
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n","\n")==response["markdown"]
        with page.expect_download() as download:
            page.get_by_role("button",name="Download Markdown").click()
        target=ROOT/"artifacts/review-announcement.md";download.value.save_as(str(target))
        assert target.read_text(encoding="utf-8")==response["markdown"]
        page.wait_for_timeout(3500);mark("end")
        page.screenshot(path=str(ROOT/"artifacts/review-export.png"))
        context.close();shutil.copyfile(video.path(),ROOT/"artifacts/review-demo.webm");browser.close()
    record={"kind":"RECORDED_REAL_DRAFT_REVIEW_REPLAY","new_inference_calls":0,"browser_api_response_replayed":True,"source_capture_output_sha256":capture["output_sha256"],"model_words_edited":False,"timeline":timeline,"raw_sha256":hashlib.sha256((ROOT/"artifacts/review-demo.webm").read_bytes()).hexdigest(),"export_identical_to_actual_model_markdown":True,"published":False}
    (ROOT/"submission/review-replay-evidence.json").write_text(json.dumps(record,indent=2),encoding="utf-8");print(json.dumps(record))


if __name__=="__main__":main()
