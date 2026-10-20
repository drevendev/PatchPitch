"""Browser MOCK checks; only the separately saved pilot uses real Gemma."""
import json

import pytest
from playwright.sync_api import sync_playwright, expect

from test_browser import ui_url
from patchpitch import generator, social
from patchpitch.models import SocialInput
from patchpitch.social_count import estimate


def result_for(body, monkeypatch):
    count=1 if body["format"]=="x_single" or body.get("operation")=="regenerate" else body["post_count"]
    raw={"posts":[{"text":f"PatchPitch keeps selected facts available for review. Draft {i+1}.","source_ids":["C03"]} for i in range(count)]}
    if body["product"]["name"]=="Idle Fantasy Shop":
        raw={"posts":[{"text":"Idle Fantasy Shop opens the Batch Board at Workshop level 10.","source_ids":["C01"]}]}
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:{"done":True,"model":"MOCK","message":{"content":json.dumps(raw)}})
    return social.generate(SocialInput.model_validate(body))


def open_page(browser,ui_url):
    context=browser.new_context(permissions=["clipboard-read","clipboard-write"])
    page=context.new_page()
    page.route("**/api/health",lambda r:r.fulfill(json={"ollama":"ready","model":"MOCK"}))
    page.goto(ui_url)
    return page


def load_and_select(page,fmt="x_thread"):
    page.locator("#load-pack").click()
    expect(page.locator("#product")).to_have_value("PatchPitch")
    assert not page.locator("#confirmed").is_checked()
    page.locator("#format").select_option(fmt)
    page.locator("#confirmed").check()


def test_thread_edit_reorder_copy_download_and_cross_product_memory(ui_url,tmp_path,monkeypatch):
    calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();page=open_page(browser,ui_url)
        def answer(route):
            body=route.request.post_data_json;calls.append(body)
            route.fulfill(json=result_for(body,monkeypatch))
        page.route("**/api/social",answer)
        load_and_select(page);page.locator("#generate").click()
        expect(page.locator(".social-card")).to_have_count(5)
        expect(page.locator(".social-card").first.get_by_role("button",name="Move up",exact=True)).to_be_disabled()
        edited="My exact edit: <script>literal text</script>."
        page.locator("#text-P03").fill(edited)
        page.locator('[data-post-id="P03"]').get_by_role("button",name="Move up",exact=True).click()
        assert page.locator(".social-card").nth(1).get_attribute("data-post-id")=="P03"
        page.locator("#media-P03").fill("Actual screenshot; not an attachment.")
        page.locator('[data-post-id="P03"]').get_by_role("button",name="Copy this post",exact=True).click()
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n","\n")==edited
        assert page.locator("#social-posts script").count()==0
        with page.expect_download() as item:page.locator("#download").click()
        assert item.value.suggested_filename.startswith("patchpitch-public-workflow-x-thread-")
        target=tmp_path/"thread.md";item.value.save_as(target)
        assert edited in target.read_text(encoding="utf-8") and "Media note (not post text)" in target.read_text(encoding="utf-8")
        page.locator("#format").select_option("x_single");page.locator("#generate").click()
        expect(page.locator(".social-card")).to_have_count(1)
        page.locator("#saved-drafts").get_by_role("button",name="X Thread",exact=True).click()
        expect(page.locator("#text-P03")).to_have_value(edited)
        page.on("dialog",lambda d:d.accept())
        page.locator("#fact-pack").select_option("idle-fantasy-shop");page.locator("#load-pack").click()
        expect(page.locator("#product")).to_have_value("Idle Fantasy Shop")
        # Existing output and export context remain tied to PatchPitch.
        with page.expect_download() as item:page.locator("#download").click()
        assert item.value.suggested_filename.startswith("patchpitch-public-workflow-x-thread-")
        page.locator("#format").select_option("x_single");page.locator("#confirmed").check()
        # For this UI-only mock, remove backup facts so the fabricated response isn't treated as model evidence.
        page.locator("#selection-panel > summary").click()
        page.get_by_role("checkbox",name="Include C08",exact=True).uncheck()
        page.locator("#confirmed").check();page.locator("#generate").click()
        expect(page.locator("#output-preset")).to_contain_text("Idle Fantasy Shop")
        assert page.locator("#saved-drafts button").count()==3
        assert len(calls)==3
        browser.close()


@pytest.mark.parametrize("failure",[409,504,502,None])
def test_regeneration_locks_and_preserves_other_edits(ui_url,monkeypatch,failure):
    pending=[];calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();page=open_page(browser,ui_url)
        page.on("dialog",lambda d:d.accept())
        def answer(route):
            body=route.request.post_data_json;calls.append(body)
            if body.get("operation")=="regenerate":pending.append(route)
            else:route.fulfill(json=result_for(body,monkeypatch))
        page.route("**/api/social",answer)
        load_and_select(page);page.locator("#generate").click();expect(page.locator(".social-card")).to_have_count(5)
        page.locator("#text-P01").fill("Keep this exact first edit.")
        page.locator("#text-P03").fill("Keep third unless replacement succeeds.")
        page.locator('[data-post-id="P03"]').get_by_role("button",name="Regenerate this post",exact=True).click()
        expect(page.locator("#text-P01")).to_be_disabled()
        assert len(pending)==1
        body=pending[0].request.post_data_json
        assert body["thread_context"][0]["text"]=="Keep this exact first edit."
        if failure:pending[0].fulfill(status=failure,json={"error":{"code":"timeout","message":"MOCK failure"}})
        else:pending[0].fulfill(json=result_for(body,monkeypatch))
        expect(page.locator("#text-P01")).to_be_enabled()
        expect(page.locator("#text-P01")).to_have_value("Keep this exact first edit.")
        if failure:expect(page.locator("#text-P03")).to_have_value("Keep third unless replacement succeeds.")
        else:assert page.locator("#text-P03").input_value().startswith("PatchPitch keeps")
        assert len(calls)==2
        browser.close()


def test_unload_guard_and_count_policy_parity(ui_url,monkeypatch):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=open_page(browser,ui_url)
        assert page.evaluate("unloadProtected") is False
        corpus=["a"*279,"a"*280,"a"*281,"Привет 漢字 😀", "👨‍👩‍👧‍👦 e\u0301", "Hi http://test.co", "https://example.com/a/very/long/path?q=1!", "www.test.co.", "example.com/x", "A\n\nCTA #Tag"]
        assert page.evaluate("texts=>texts.map(socialLength)",corpus)==[estimate(t) for t in corpus]
        page.route("**/api/social",lambda r:r.fulfill(json=result_for(r.request.post_data_json,monkeypatch)))
        load_and_select(page,"x_single");page.locator("#generate").click();expect(page.locator(".social-card")).to_have_count(1)
        page.locator("#text-P01").fill("Keep my edit.")
        dialogs=[]
        page.on("dialog",lambda d:(dialogs.append(d.type),d.dismiss()))
        page.evaluate("setTimeout(()=>location.reload(),0)")
        page.wait_for_timeout(200)
        assert dialogs==["beforeunload"]
        expect(page.locator("#text-P01")).to_have_value("Keep my edit.")
        page.locator("#text-P01").fill("漢"*141)
        expect(page.locator(".social-count")).to_contain_text("over limit")
        browser.close()


def test_import_failure_and_clipboard_denial_preserve_text(ui_url,monkeypatch):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=open_page(browser,ui_url)
        page.route("**/api/social",lambda r:r.fulfill(json=result_for(r.request.post_data_json,monkeypatch)))
        load_and_select(page,"x_single");page.locator("#generate").click();expect(page.locator(".social-card")).to_have_count(1)
        page.locator("#text-P01").fill("My current text.")
        page.on("dialog",lambda d:d.accept())
        page.locator("#pack-file").set_input_files({"name":"broken.json","mimeType":"application/json","buffer":b'{"schema_version":2}'})
        expect(page.locator("#error")).to_be_visible()
        expect(page.locator("#text-P01")).to_have_value("My current text.")
        expect(page.locator("#product")).to_have_value("PatchPitch")
        page.evaluate("()=>{navigator.clipboard.writeText=()=>Promise.reject(new Error('MOCK denied'));}")
        page.locator("#copy").click()
        expect(page.locator("#error")).to_contain_text("Clipboard unavailable")
        expect(page.locator("#text-P01")).to_have_value("My current text.")
        names=page.evaluate("()=>['CON','a/b:c','Игра 😀','...'].map(product=>exportName({context:{product,release_label:'0.2',generated_at:'2026-10-20T12:00:00Z'},presentation:{format:'x_single'}}))")
        assert len(set(names))==4 and all('/' not in n and ':' not in n for n in names)
        browser.close()
