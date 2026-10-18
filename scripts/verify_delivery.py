"""Verify local delivery assets and the separate static sample, without inference."""
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools"/"browsers"))
from playwright.sync_api import sync_playwright


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    capture=json.loads((ROOT/"submission/capture-evidence.json").read_text(encoding="utf-8"))
    assert capture["status"]=="EXERCISED"
    layouts=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":1440,"height":1000})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto("http://127.0.0.1:8000",wait_until="networkidle")
        page.get_by_role("button",name="Try an example").click()
        page.locator("#selection-panel").wait_for(state="visible")
        # Replaying the saved response here tests layout only. Live inference is
        # separately evidenced by capture_demo.py; never count this as a call.
        page.route("**/api/pitch",lambda route:route.fulfill(json=capture["response"]))
        page.get_by_label("I confirm the selected changes").check()
        page.get_by_role("button",name="Write the announcement").click()
        page.locator("#result").wait_for(state="visible")
        for width,height in [(1920,1080),(1440,900),(1366,768),(390,844)]:
            page.set_viewport_size({"width":width,"height":height})
            page.wait_for_timeout(350)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.get_by_label("Product name").is_visible()
            doc_height=page.evaluate("document.documentElement.scrollHeight")
            layouts.append({"width":width,"height":height,"document_height":doc_height,"horizontal_scroll":False})
            page.screenshot(path=str(ROOT/"artifacts"/f"layout-{width}.png"),full_page=True)
            if width>760:assert doc_height<=height,f"Desktop overflow at {width}: {doc_height}>{height}"
        requests=[]
        page.on("request",lambda r:requests.append(r.url))
        page.set_viewport_size({"width":1440,"height":1000})
        page.goto("http://127.0.0.1:8001",wait_until="networkidle")
        assert "SAMPLE" in page.locator(".sample").inner_text()
        assert page.get_by_role("button",name="Write the announcement").count()==0
        assert not any("/api/" in url or ":11434" in url or ":8000" in url for url in requests)
        page.locator("video").evaluate("v => v.load()")
        page.wait_for_function("document.querySelector('video').readyState >= 2")
        assert 55<=page.locator("video").evaluate("v => v.duration")<=65
        page.locator("video").evaluate("v => { v.muted = true; return v.play(); }")
        page.wait_for_timeout(500)
        assert not page.locator("video").evaluate("v => v.paused")
        page.screenshot(path=str(ROOT/"artifacts"/"static-sample.png"),full_page=True)
        assert not errors,errors
        browser.close()
    report={"status":"PASSED","live_app_layouts":layouts,"layout_model_response":"RECORDED_OUTPUT_REPLAY_FOR_LAYOUT_ONLY","layout_inference_calls":0,"static_sample":"RECORDED_SAMPLE","sample_video_playback":True,"sample_api_calls":0,"browser_errors":errors,"command":"python scripts/verify_delivery.py","exit_code":0}
    (ROOT/"submission"/"delivery-check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))


if __name__=="__main__":main()
