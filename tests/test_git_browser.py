"""Git → review → editable DevLog → Save/Open. Actual Git, MOCK inference."""
import json

from playwright.sync_api import expect, sync_playwright

from patchpitch import generator, git_import
from patchpitch.models import PitchInput
from test_browser import ui_url
from test_git_import import git_repository


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
