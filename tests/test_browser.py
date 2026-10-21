"""MOCK browser tests; never evidence of actual Gemma generation."""
import json
import os
import socket
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
    # Separate test runs must not borrow and later lose another run's server.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url=f"http://127.0.0.1:{port}"
    process=subprocess.Popen([sys.executable,"-m","uvicorn","patchpitch.app:app","--host","127.0.0.1","--port",str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            if process.poll() is not None:
                pytest.fail("Test server exited before it became ready")
            try:
                with urllib.request.urlopen(url,timeout=1): break
            except OSError: time.sleep(.1)
        else: pytest.fail("Test server did not start")
        yield url
    finally:
        process.terminate();process.wait(timeout=10)


def test_browser_mock_review_edit_export(ui_url,tmp_path,input_data):
    from playwright.sync_api import sync_playwright
    calls=[]
    response={"draft":{"title":{"text":"<img src=x onerror=window.xss=1>","source_ids":["C01"]},"intro":{"text":"MOCK browser output","source_ids":["C01"]},"highlights":[{"text":"Search your notes.","source_ids":["C01"]}],"note":None},"markdown":"# MOCK\n\nDraft.\n","warnings":[],"sources":{"C01":"<script>window.xss=2</script>"},"source_map":[{"block":"Title","source_ids":["C01"]}],"meta":{"model":"MOCK","elapsed_seconds":1.2}}
    response["draft"]["highlights"][0]["retained_facts"]=["Only titles are searched."]
    response["draft"]["details"]=[{"text":"An additional change.","source_ids":["C01"]}]
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
        page.locator("#selection-panel > summary").click()
        assert not page.get_by_role("checkbox",name="Include C04").is_checked()
        page.locator("#selection-panel > summary").click()
        page.get_by_label("I confirm the selected changes").check()
        page.get_by_role("button",name="Write the announcement").click()
        page.locator("#result").wait_for(state="visible")
        assert len(calls)==1 and not calls[0]["changes"][3]["include"]
        assert page.locator("#draft-view img").count()==0 and page.evaluate("window.xss") is None
        assert "Only titles are searched." in page.locator("#draft-view").inner_text()
        assert page.locator(".more-changes").get_attribute("open") is None
        page.locator(".more-changes > summary").click()
        assert page.get_by_text("An additional change.",exact=True).is_visible()
        page.locator("#sources > summary").click()
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


def test_browser_explains_a_stale_backend(ui_url,input_data):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.route("**/static/example.json",lambda route:route.fulfill(json=input_data))
        page.route("**/api/pitch",lambda route:route.fulfill(status=422,json={"detail":[{"type":"extra_forbidden","loc":["body","voice_reference"],"msg":"Extra inputs are not permitted"}]}))
        page.goto(ui_url)
        page.get_by_role("button",name="Try an example").click()
        page.get_by_label("I confirm the selected changes").check()
        page.get_by_role("button",name="Write the announcement").click()
        page.locator("#error").wait_for(state="visible")
        assert "Restart PatchPitch" in page.locator("#error").inner_text()
        assert page.locator("#product").input_value()==input_data["product"]["name"]
        browser.close()


@pytest.mark.parametrize("failure",[None,"example","prepare"])
def test_example_loading_and_generation_cannot_overlap(ui_url,input_data,draft_data,failure):
    """Hold both operations; failed loading must preserve input and edited prose."""
    from playwright.sync_api import sync_playwright,expect
    original="# Original draft\n\nKeep these words.\n"
    edited="# My edited draft\n\nStill here.\n"
    response={"draft":draft_data,"markdown":original,"warnings":[],"sources":{},"source_map":[],"meta":{"model":"MOCK","elapsed_seconds":1.0}}
    example=json.loads(json.dumps(input_data));example["product"]["name"]="Delayed example"
    examples=[];pitches=[];pending_example=[];pending_pitch=[];preparations=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(permissions=["clipboard-read","clipboard-write"]);page=context.new_page()
        def load_example(route):
            examples.append(route)
            if len(examples)==1:route.fulfill(json=input_data)
            else:pending_example.append(route)
        def prepare_example(route):
            preparations.append(route)
            if failure=="prepare" and len(preparations)==2:
                route.fulfill(status=422,json={"detail":"MOCK preparation failure"})
            else:route.continue_()
        def generate(route):
            pitches.append(route.request.post_data_json)
            if len(pitches)==1:route.fulfill(json=response)
            else:pending_pitch.append(route)
        page.route("**/static/example.json",load_example)
        page.route("**/api/prepare",prepare_example)
        page.route("**/api/pitch",generate)
        page.goto(ui_url);page.locator("#example").click();page.locator("#confirmed").check();page.locator("#generate").click()
        page.locator("#result").wait_for(state="visible");page.locator("#edit").click();page.locator("#editor").fill(edited)
        page.once("dialog",lambda d:d.accept());page.locator("#example").click()
        expect(page.locator("#generate")).to_be_disabled()
        expect(page.locator("#editor")).to_be_disabled()
        assert len(pending_example)==1
        page.locator("#pitch-form").dispatch_event("submit")
        assert len(pitches)==1 and page.locator("#product").input_value()==input_data["product"]["name"]
        if failure=="example":pending_example[0].fulfill(status=503,json={})
        else:pending_example[0].fulfill(json=example)
        expect(page.locator("#generate")).to_be_enabled()
        expected_name=input_data["product"]["name"] if failure else "Delayed example"
        assert page.locator("#product").input_value()==expected_name
        assert page.locator("#editor").input_value()==edited
        assert page.locator("#editor").is_enabled()
        if failure:assert page.locator("#error").is_visible()
        page.locator("#confirmed").check()
        page.once("dialog",lambda d:d.accept());page.locator("#generate").click()
        expect(page.locator("#example")).to_be_disabled()
        page.locator("#example").dispatch_event("click")
        assert len(examples)==2 and len(pending_pitch)==1
        assert pitches[-1]["product"]["name"]==expected_name
        assert page.locator("#product").input_value()==expected_name
        pending_pitch[0].fulfill(json={**response,"markdown":"# Correct response\n\nSame request.\n"})
        expect(page.locator("#example")).to_be_enabled()
        page.locator("#copy").click()
        assert page.evaluate("() => navigator.clipboard.readText()").replace("\r\n","\n")=="# Correct response\n\nSame request.\n"
        browser.close()


@pytest.mark.parametrize("fails",[False,True])
def test_delayed_regeneration_locks_editor_and_restores_it(ui_url,input_data,draft_data,fails):
    from playwright.sync_api import sync_playwright
    response={"draft":draft_data,"markdown":"# First\n\nOriginal.\n","warnings":[],"sources":{"C01":"A fact."},"source_map":[],"meta":{"model":"MOCK","elapsed_seconds":1.0}}
    pending=[];calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.route("**/static/example.json",lambda route:route.fulfill(json=input_data))
        def route_pitch(route):
            calls.append(1)
            if len(calls)==1:route.fulfill(json=response)
            else:pending.append(route)
        page.route("**/api/pitch",route_pitch)
        page.goto(ui_url);page.locator("#example").click();page.locator("#confirmed").check();page.locator("#generate").click()
        page.locator("#result").wait_for(state="visible")
        page.locator("#edit").click();page.locator("#editor").fill("# My previous edit\n\nKeep this.\n")
        page.once("dialog",lambda dialog:dialog.accept());page.locator("#generate").click()
        page.wait_for_function("document.getElementById('generate').disabled")
        assert page.locator("#edit").is_disabled() and page.locator("#editor").is_disabled()
        assert page.locator("#format").is_disabled() and page.locator("#style").is_disabled()
        assert page.locator("#editor").input_value()=="# My previous edit\n\nKeep this.\n"
        assert len(pending)==1
        if fails:pending[0].fulfill(status=504,json={"error":{"code":"timeout","message":"MOCK timeout"}})
        else:pending[0].fulfill(json={**response,"markdown":"# Second\n\nNew draft.\n"})
        page.wait_for_function("!document.getElementById('generate').disabled")
        assert page.locator("#edit").is_enabled() and page.locator("#editor").is_enabled()
        if fails:
            assert page.locator("#editor").input_value()=="# My previous edit\n\nKeep this.\n"
            assert page.locator("#editor").is_visible()
            assert page.locator("#error").inner_text()=="MOCK timeout"
        else:
            page.locator("#edit").click()
            assert page.locator("#editor").input_value()=="# Second\n\nNew draft.\n"
        browser.close()


def test_formats_tags_and_edited_variants_export_exactly(ui_url,tmp_path,input_data,draft_data):
    from playwright.sync_api import sync_playwright
    calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(permissions=["clipboard-read","clipboard-write"]);page=context.new_page()
        page.route("**/static/example.json",lambda route:route.fulfill(json=input_data))
        def route_pitch(route):
            body=route.request.post_data_json;calls.append(body)
            short=body["format"]=="short"
            base="Find notes by title.\n\nOriginal CTA.\n" if short else "# My devlog\n\nA full draft.\n"
            draft={"text":"Find notes by title.","source_ids":["C01"],"hashtags":["#PocketOrchard"]} if short else draft_data
            route.fulfill(json={"draft":draft,"markdown":base+("\n#PocketOrchard\n" if short else ""),"body_markdown":base,
                "warnings":[],"sources":{"C01":"Search notes by title."},"source_map":[{"block":"Post","source_ids":["C01"]}],"omitted_source_ids":["C02","C03"] if short else [],
                "presentation":{"format":body["format"],"format_label":"Short post" if short else "Devlog","style":body["style"],"style_label":body["style"].title(),"limit":280 if short else None,"cta_text":"Original CTA." if short else ""},"meta":{"model":"MOCK","elapsed_seconds":1.0}})
        page.route("**/api/pitch",route_pitch)
        page.goto(ui_url);page.locator("#example").click();page.locator("#confirmed").check();page.locator("#generate").click()
        page.locator("#result").wait_for(state="visible");page.locator("#edit").click()
        manual="# My saved edit\n\nKeep my voice.\n";page.locator("#editor").fill(manual)
        page.locator("#format").select_option("short");page.locator("#style").select_option("lively");page.locator("#auto-tags").check();page.locator("#generate").click()
        page.get_by_role("button",name="Remove #PocketOrchard",exact=True).wait_for()
        assert calls[-1]["format"]=="short" and calls[-1]["style"]=="lively" and calls[-1]["auto_tags"] is True
        assert "C02, C03" in page.locator(".omission-note").inner_text()
        page.get_by_role("button",name="Remove #PocketOrchard",exact=True).click()
        page.locator("#copy").click()
        expected="Find notes by title.\n\nOriginal CTA.\n"
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n","\n")==expected
        # Pending input edits cannot change the CTA attached to the saved output.
        page.locator("#writing-options > summary").click();page.locator("#cta").fill("A different CTA.")
        assert page.locator(".draft-cta").inner_text()=="Original CTA."
        page.locator("#saved-drafts").get_by_role("button",name="Devlog",exact=True).click()
        assert page.locator("#editor").input_value()==manual
        page.locator("#copy").click()
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n","\n")==manual
        page.locator("#saved-drafts").get_by_role("button",name="Short post",exact=True).click()
        assert page.locator("#tag-chips button").count()==0
        with page.expect_download() as download:page.locator("#download").click()
        target=tmp_path/"short.md";download.value.save_as(target)
        assert target.read_text(encoding="utf-8")==expected
        page.locator("#edit").click();page.locator("#editor").fill("x"*281)
        assert "281 / 280 characters · over limit" in page.locator("#character-count").inner_text()
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


@pytest.mark.parametrize("reduced",["no-preference","reduce"])
def test_disclosure_reversal_and_keyboard(ui_url,reduced,input_data):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(reduced_motion=reduced)
        page.route("**/static/example.json",lambda route:route.fulfill(json=input_data))
        page.goto(ui_url)
        page.get_by_role("button",name="Try an example").click()
        summary=page.locator("#selection-panel > summary")
        summary.wait_for(state="visible")
        # Reverse an animation before its previous transition can finish.
        for _ in range(3):
            summary.click(force=True)
            page.wait_for_timeout(35)
        page.wait_for_timeout(320)
        assert page.locator("#selection-panel").get_attribute("open") is not None
        assert page.get_by_role("checkbox",name="Include C01").is_visible()
        page.locator("#product").evaluate("el => el.focus()")
        assert page.evaluate("document.activeElement.id") != "product"
        summary.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(320)
        assert page.locator("#selection-panel").get_attribute("open") is None
        assert page.get_by_label("Product name").is_visible()
        assert page.evaluate("!document.querySelector('#selection-panel').getAnimations().length")
        assert page.locator("#selection-panel").evaluate("el => !el.style.height && !el.style.overflow")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        browser.close()


def test_long_highlight_preview_preserves_complete_export(ui_url,input_data):
    from playwright.sync_api import sync_playwright
    text="Keep the full original explanation available while showing a compact preview. "*9
    markdown="# Full announcement\n\n"+text+"\n"
    response={"draft":{"title":{"text":"Full announcement","source_ids":["C01"]},"intro":{"text":"A short introduction.","source_ids":["C01"]},"highlights":[{"text":text,"source_ids":["C01"]}],"details":[],"note":None},"markdown":markdown,"warnings":[],"sources":{"C01":"Original source."},"source_map":[{"block":"Highlight 1","source_ids":["C01"]}],"meta":{"model":"MOCK","elapsed_seconds":1}}
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(permissions=["clipboard-read","clipboard-write"])
        page=context.new_page()
        page.route("**/static/example.json",lambda route:route.fulfill(json=input_data))
        page.route("**/api/pitch",lambda route:route.fulfill(json=response))
        page.goto(ui_url)
        page.get_by_role("button",name="Try an example").click()
        page.get_by_label("I confirm the selected changes").check()
        page.get_by_role("button",name="Write the announcement").click()
        detail=page.locator(".highlight");detail.wait_for(state="visible")
        assert page.locator(".highlight-text").text_content()==text
        assert "\u2197" in page.locator("#example").inner_text()
        initial=detail.bounding_box()["height"]
        detail.locator("summary").click();page.wait_for_timeout(320)
        assert detail.bounding_box()["height"]>initial
        detail.locator("summary").click();page.wait_for_timeout(320)
        assert abs(detail.bounding_box()["height"]-initial)<1
        page.get_by_role("button",name="Copy Markdown",exact=True).click()
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n","\n")==markdown
        browser.close()
