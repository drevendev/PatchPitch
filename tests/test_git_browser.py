"""Git → review → editable DevLog → Save/Open. Actual Git, MOCK inference."""
import json

from playwright.sync_api import expect, sync_playwright

from patchpitch import generator, git_import
from patchpitch.models import PitchInput
from test_browser import ui_url
from test_git_import import git_repository, large_git_repository


def test_git_to_devlog_and_restored_publication_baseline(ui_url, git_repository, monkeypatch, tmp_path):
    root, base, head = git_repository
    calls = []
    def model(path, payload, timeout):
        calls.append(payload)
        return {"done": True, "model": "MOCK", "message": {"content": json.dumps({"facts": [
            {"text": "The limit changed from 1 to 3.", "evidence_ids": ["D01"], "kind": "implemented"}]})}}
    monkeypatch.setattr(generator, "ollama_json", model)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = browser.new_page()
        dialog_handler = lambda d: d.accept()
        page.on("dialog", dialog_handler)
        page.route("**/api/health", lambda r: r.fulfill(json={"ollama": "ready", "model": "MOCK"}))
        def facts(route): route.fulfill(json=git_import.extract(git_import.ExtractInput.model_validate(route.request.post_data_json)))
        page.route("**/api/git/facts", facts)
        bodies = []
        def write(route):
            body = route.request.post_data_json; bodies.append(body)
            block = {"text": "The limit changed from 1 to 3.", "source_ids": ["C01"], "retained_facts": []}
            draft = {"title": {**block, "text": "A development limit change"}, "intro": block,
                "highlights": [block], "details": [], "note": None, "hashtags": []}
            monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: {"done": True, "model": "MOCK", "message": {"content": json.dumps(draft)}})
            route.fulfill(json=generator.generate(PitchInput.model_validate(body)))
        page.route("**/api/pitch", write)
        page.goto(ui_url); page.locator("#git-tools > summary").click()
        page.locator("#git-repo").fill(str(root)); page.locator("#git-count").fill("1"); page.locator("#git-inspect").click()
        expect(page.locator("#git-summary")).to_contain_text(head)
        assert not calls
        assert page.evaluate("hasSessionContent()")
        assert page.evaluate("!window.dispatchEvent(new Event('beforeunload', {cancelable:true}))")
        page.get_by_role("checkbox", name="Use file feature.py", exact=True).check()
        page.locator("#git-preview").click(); expect(page.locator("#git-reviewed")).to_be_enabled()
        assert not calls
        page.locator("#git-reviewed").check(); page.locator("#git-extract").click()
        expect(page.get_by_role("checkbox", name="Use fact 1", exact=True)).to_be_visible()
        assert len(calls) == 1
        page.get_by_role("checkbox", name="Use fact 1", exact=True).check()
        page.get_by_role("textbox", name="Review fact 1", exact=True).fill("The limit changed from 1 to 3; review confirmed this code change.")
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event: page.locator("#save-session").click()
        unfinished = tmp_path/"unfinished-git-review.json"; event.value.save_as(unfinished)
        # Git-only work must receive the same replacement guard as writing drafts.
        page.remove_listener("dialog", dialog_handler)
        replacements = []
        def dismiss_replacement(dialog):
            replacements.append(dialog.message)
            dialog.dismiss()
        page.once("dialog", dismiss_replacement)
        page.locator("#open-session").set_input_files(unfinished)
        expect(page.locator("#save-session")).to_be_enabled()
        assert replacements and "Replace this tab" in replacements[0]
        expect(page.get_by_role("textbox", name="Review fact 1", exact=True)).to_have_value("The limit changed from 1 to 3; review confirmed this code change.")
        page.on("dialog", dialog_handler)
        page.reload(); page.locator("#open-session").set_input_files(unfinished)
        page.locator("#git-tools > summary").click()
        expect(page.get_by_role("checkbox", name="Use fact 1", exact=True)).to_be_checked()
        expect(page.get_by_role("textbox", name="Review fact 1", exact=True)).to_have_value("The limit changed from 1 to 3; review confirmed this code change.")
        expect(page.locator("#git-reviewed")).not_to_be_checked()
        assert len(calls) == 1
        page.locator("#git-preview").click()
        expect(page.locator("#git-reviewed")).to_be_enabled()
        expect(page.get_by_role("textbox", name="Review fact 1", exact=True)).to_have_value("The limit changed from 1 to 3; review confirmed this code change.")
        page.locator("#git-reviewed").check()
        page.remove_listener("dialog", dialog_handler); page.once("dialog", lambda d: d.dismiss())
        page.locator("#git-extract").click()
        assert len(calls) == 1
        page.on("dialog", dialog_handler)
        page.locator("#git-apply").click()
        expect(page.locator("#writing-goal")).to_have_value("development")
        expect(page.locator("#confirmed")).not_to_be_checked()
        page.locator("#confirmed").check(); page.locator("#generate").click()
        expect(page.locator("#output-preset")).to_contain_text(head[:12])
        assert bodies[0]["source_context"]["base"] == base
        assert bodies[0]["source_references"][0]["source_ref"].endswith("D01 feature.py")
        page.locator("#edit").click(); page.locator("#editor").fill("# My DevLog\n\nТочные правки.\n")
        # Synthetic publication marker in a MOCK test: no external page is accessed.
        page.locator("#result-tools > details.optional-input > summary").click()
        page.locator("#published-url").fill("https://example.org/mock-published-devlog")
        page.locator("#record-publication").click()
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event: page.locator("#save-session").click()
        saved = tmp_path/"git-session.json"; event.value.save_as(saved)
        page.reload(); page.locator("#open-session").set_input_files(saved)
        expect(page.locator("#editor")).to_be_visible()
        expect(page.locator("#editor")).to_have_value("# My DevLog\n\nТочные правки.\n")
        assert len(bodies) == 1 and len(calls) == 1
        assert page.evaluate("Object.values(publicationMarkers)[0].head") == head
        assert head in page.locator("#source-list").text_content()
        browser.close()


def test_large_diff_failure_save_open_resume_and_review(ui_url, large_git_repository, monkeypatch, tmp_path):
    root,base,head=large_git_repository
    requests=[]
    failed_once=False
    def model(path,payload,timeout):
        ids=payload["format"]["$defs"]["Candidate"]["properties"]["evidence_ids"]["items"]["enum"]
        return {"done":True,"model":"MOCK","message":{"content":json.dumps({"facts":[
            {"text":"Committed values were added in this part.","kind":"implemented","evidence_ids":[ids[0]]}]})}}
    monkeypatch.setattr(generator,"ollama_json",model)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(); page=browser.new_page(); page.on("dialog",lambda d:d.accept())
        page.route("**/api/health",lambda r:r.fulfill(json={"ollama":"ready","model":"MOCK"}))
        def extract(route):
            nonlocal failed_once
            body=route.request.post_data_json;requests.append(body["batch_index"])
            if body["batch_index"]==1 and not failed_once:
                failed_once=True
                route.fulfill(status=502,json={"error":{"code":"invalid_draft","message":"MOCK failed second batch"},
                    "evidence":{"raw_response":{"message":{"content":"Original invalid batch output"}}}})
            else: route.fulfill(json=git_import.extract(git_import.ExtractInput.model_validate(body)))
        page.route("**/api/git/facts",extract)
        page.goto(ui_url);page.locator("#git-tools > summary").click()
        page.locator("#git-repo").fill(str(root));page.locator("#git-count").fill("1");page.locator("#git-inspect").click()
        expect(page.locator("#git-summary")).to_contain_text(head)
        page.get_by_role("checkbox",name="Use file feature.py",exact=True).check()
        page.locator("#git-preview").click();expect(page.locator("#git-reviewed")).to_be_enabled()
        count=page.evaluate("gitState.preview.chunking.batches.length")
        assert count>1
        assert page.locator("#git-diffs details").count()>1
        page.locator("#git-reviewed").check();page.locator("#git-extract").click()
        expect(page.locator("#error")).to_contain_text("MOCK failed second batch")
        expect(page.locator("#git-apply")).to_be_disabled()
        assert requests==[0,1]
        page.get_by_role("textbox",name="Review fact 1",exact=True).fill("Keep this exact reviewed text.\n")
        page.get_by_role("checkbox",name="Use fact 1",exact=True).check()
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event:page.locator("#save-session").click()
        saved=tmp_path/"partial.json";event.value.save_as(saved)
        original=json.loads(saved.read_text(encoding="utf-8"))
        assert original["git_review"]["record"]["attempts"][1]["response"]["raw_response"]["message"]["content"]=="Original invalid batch output"
        page.reload();page.locator("#open-session").set_input_files(saved)
        page.locator("#git-tools > summary").click()
        expect(page.get_by_role("textbox",name="Review fact 1",exact=True)).to_have_value("Keep this exact reviewed text.\n")
        expect(page.get_by_role("checkbox",name="Use fact 1",exact=True)).to_be_checked()
        expect(page.locator("#git-reviewed")).not_to_be_checked()
        expect(page.locator("#git-extract")).to_be_disabled()
        assert requests==[0,1]
        page.locator("#git-reviewed").check();page.locator("#git-extract").click()
        expect(page.locator("#git-progress")).to_contain_text(" · complete ·",timeout=30000)
        expect(page.locator("#git-apply")).to_be_enabled()
        assert requests==[0,1,*range(1,count)]
        expect(page.get_by_role("textbox",name="Review fact 1",exact=True)).to_have_value("Keep this exact reviewed text.\n")
        page.get_by_role("button",name="Review D01",exact=False).first.click()
        assert page.locator("#git-evidence-D01").get_attribute("open") is not None
        page.locator("#git-apply").click()
        assert page.evaluate("changes.map(c=>c.text)")==["Keep this exact reviewed text.\n"]
        assert "part 1/" in page.evaluate("packContext.source_references[0].source_ref")
        assert page.evaluate("packContext.source_context.head")==head
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event:page.locator("#save-session").click()
        complete=tmp_path/"complete.json";event.value.save_as(complete)
        page.reload();page.locator("#open-session").set_input_files(complete)
        expect(page.locator("#product")).to_have_value(root.name)
        assert requests==[0,1,*range(1,count)]
        browser.close()


def test_stop_then_continue_keeps_large_candidate_pool_and_applies_only_selected(ui_url, large_git_repository, monkeypatch):
    root,base,head=large_git_repository
    requests,pending=[],[]
    def model(path,payload,timeout):
        ids=payload["format"]["$defs"]["Candidate"]["properties"]["evidence_ids"]["items"]["enum"]
        return {"done":True,"model":"MOCK","message":{"content":json.dumps({"facts":[
            {"text":f"MOCK candidate {ids[0]} number {i+1}: value definitions changed.","kind":"implemented","evidence_ids":[ids[0]]}
            for i in range(8)]})}}
    monkeypatch.setattr(generator,"ollama_json",model)
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page();page.on("dialog",lambda d:d.accept())
        page.route("**/api/health",lambda r:r.fulfill(json={"ollama":"ready","model":"MOCK"}))
        def extract(route):
            body=route.request.post_data_json;requests.append(body["batch_index"])
            if not pending:pending.append(route)
            else:route.fulfill(json=git_import.extract(git_import.ExtractInput.model_validate(body)))
        page.route("**/api/git/facts",extract)
        page.goto(ui_url);page.locator("#git-tools > summary").click()
        page.locator("#git-repo").fill(str(root));page.locator("#git-count").fill("1");page.locator("#git-inspect").click()
        expect(page.locator("#git-summary")).to_contain_text(head)
        page.get_by_role("checkbox",name="Use file feature.py",exact=True).check()
        page.locator("#git-preview").click();expect(page.locator("#git-reviewed")).to_be_enabled()
        count=page.evaluate("gitState.preview.chunking.batches.length")
        page.locator("#git-reviewed").check();page.locator("#git-extract").click()
        expect(page.locator("#git-stop")).to_be_enabled();page.locator("#git-stop").click()
        assert requests==[0]
        pending[0].fulfill(json=git_import.extract(git_import.ExtractInput.model_validate(pending[0].request.post_data_json)))
        expect(page.locator("#git-progress")).to_contain_text(" · stopped ·")
        assert requests==[0]
        expect(page.locator("#git-apply")).to_be_disabled()
        page.get_by_role("textbox",name="Review fact 1",exact=True).fill("An edit retained through continuation.")
        page.locator("#git-extract").click()
        expect(page.locator("#git-progress")).to_contain_text(" · complete ·",timeout=30000)
        assert requests==list(range(count))
        expect(page.get_by_role("textbox",name="Review fact 1",exact=True)).to_have_value("An edit retained through continuation.")
        pool_count=page.locator("#git-candidates section").count()
        assert pool_count>15
        selected=page.get_by_role("textbox",name="Review fact 17",exact=True).input_value()
        page.get_by_role("checkbox",name="Use fact 17",exact=True).check()
        page.locator("#git-apply").click()
        assert page.evaluate("changes.map(c=>c.text)")==[selected]
        assert page.evaluate("packContext.source_references[0].stable_id")=="G017"
        assert page.evaluate("gitState.facts.length")==pool_count
        assert page.evaluate("changes[0].id")=="C01"
        browser.close()
