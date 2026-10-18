"""Verify local delivery assets and the separate static sample, without inference."""
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools"/"browsers"))
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":1440,"height":1000})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto("http://127.0.0.1:8000",wait_until="networkidle")
        page.get_by_role("button",name="Try an example").click()
        page.get_by_role("checkbox",name="Include C05").wait_for()
        for width,height in [(1440,1000),(390,844)]:
            page.set_viewport_size({"width":width,"height":height})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.get_by_label("Product name").is_visible()
            page.screenshot(path=str(ROOT/"artifacts"/f"layout-{width}.png"),full_page=True)
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
    report={"status":"PASSED","live_app_layouts":[1440,390],"static_sample":"RECORDED_SAMPLE","sample_video_playback":True,"sample_api_calls":0,"browser_errors":errors,"command":"python scripts/verify_delivery.py","exit_code":0}
    (ROOT/"submission"/"delivery-check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))


if __name__=="__main__":main()
