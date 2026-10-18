"""MOCK browser tests; never evidence of actual Gemma generation."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools"/"browsers"))


@pytest.fixture(scope="module")
def ui_url():
    process=subprocess.Popen([sys.executable,"-m","uvicorn","patchpitch.app:app","--host","127.0.0.1","--port","8765"],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/",timeout=1): break
            except OSError: time.sleep(.1)
        else: pytest.fail("Test server did not start")
        yield "http://127.0.0.1:8765"
    finally:
        process.terminate();process.wait(timeout=10)


def test_browser_mock_review_edit_export(ui_url,tmp_path,input_data):
    from playwright.sync_api import sync_playwright
    calls=[]
    response={"draft":{"title":{"text":"<img src=x onerror=window.xss=1>","source_ids":["C01"]},"intro":{"text":"MOCK browser output","source_ids":["C01"]},"highlights":[{"text":"Search your notes.","source_ids":["C01"]}],"note":None},"markdown":"# MOCK\n\nDraft.\n","warnings":[],"sources":{"C01":"<script>window.xss=2</script>"},"source_map":[{"block":"Title","source_ids":["C01"]}],"meta":{"model":"MOCK","elapsed_seconds":1.2}}
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(permissions=["clipboard-read","clipboard-write"])
        page=context.new_page()
        page.route("**/static/example.json",lambda route:route.fulfill(json=input_data))
        def mock(route):
            calls.append(route.request.post_data_json)
            time.sleep(.2)
            route.fulfill(json=response)
        page.route("**/api/pitch",mock)
        page.goto(ui_url)
        page.get_by_role("button",name="Try an example").click()
        assert not page.get_by_role("checkbox",name="Include C04").is_checked()
        page.get_by_label("I confirm the selected changes").check()
        page.get_by_role("button",name="Write the announcement").click()
        page.locator("#result").wait_for(state="visible")
        assert len(calls)==1 and not calls[0]["changes"][3]["include"]
        assert page.locator("#draft-view img").count()==0 and page.evaluate("window.xss") is None
        page.locator("#sources summary").click()
        assert page.locator("#source-list script").count()==0
        page.get_by_role("button",name="Edit draft",exact=True).click()
        edited="# My edited draft\n\nMy final words.\n"
        page.locator("#editor").fill(edited)
        assert page.locator("#edited-label").is_visible()
        page.get_by_role("button",name="Copy Markdown",exact=True).click()
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n") == edited
        with page.expect_download() as download:
            page.get_by_role("button",name="Download Markdown").click()
        target=tmp_path/"draft.md";download.value.save_as(target)
        assert target.read_text()==edited
        page.once("dialog",lambda dialog:dialog.dismiss())
        page.get_by_role("button",name="Write the announcement").click()
        assert page.locator("#editor").input_value()==edited and len(calls)==1
        browser.close()


@pytest.mark.parametrize("code,message",[("timeout","The local model timed out."),("ollama_unavailable","Start Ollama and try again.")])
def test_browser_mock_failure_preserves_input(ui_url,code,message,input_data):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.route("**/static/example.json",lambda route:route.fulfill(json=input_data))
        page.route("**/api/pitch",lambda route:route.fulfill(status=503,json={"error":{"code":code,"message":message}}))
        page.goto(ui_url)
        page.get_by_role("button",name="Try an example").click()
        page.get_by_label("I confirm the selected changes").check()
        page.get_by_role("button",name="Write the announcement").click()
        page.locator("#error").wait_for(state="visible")
        assert page.locator("#product").input_value()=="Pocket Orchard"
        assert page.locator("#error").inner_text()==message
        assert page.locator("#result").is_hidden()
        browser.close()
