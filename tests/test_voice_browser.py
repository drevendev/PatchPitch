"""Real browser/file roundtrip with synthetic voice and explicitly mocked inference."""
import json
from playwright.sync_api import expect, sync_playwright
from test_browser import ui_url
from test_voice import voice_bundle
from patchpitch import generator
from patchpitch.models import PitchInput


def test_voice_import_export_restore_and_failure_preserve_edits(ui_url, voice_bundle, tmp_path, monkeypatch):
    artifact=tmp_path/"voice-bundle.json"
    artifact.write_text(json.dumps(voice_bundle),encoding="utf-8")
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(accept_downloads=True)
        page.on("dialog",lambda d:d.accept())
        page.goto(ui_url)
        page.locator("#voice-file").set_input_files(artifact)
        expect(page.locator("#style")).to_have_value("voice")
        expect(page.locator("#format")).to_have_value("telegram")
        expect(page.locator("#language")).to_have_value("ru")
        page.locator("#product").fill("Synthetic Notebook")
        page.locator("#description").fill("Local notes")
        page.locator("#audience").fill("Notebook readers")
        page.locator("#changes").fill("Можно искать заметки по названию.")
        expect(page.locator("#selection-count")).to_contain_text("1 selected")
        calls=[]
        def answer(route):
            body=route.request.post_data_json;calls.append(body)
            monkeypatch.setattr(generator,"ollama_json",lambda *a,**k:{"done":True,"model":"MOCK","message":{"content":json.dumps({"text":"Теперь заметки можно искать по названию.","source_ids":["C01"],"hashtags":[]})}})
            route.fulfill(json=generator.generate(PitchInput.model_validate(body)))
        page.route("**/api/pitch",answer)
        page.locator("#confirmed").check();page.locator("#generate").click()
        expect(page.locator("#output-preset")).to_contain_text(voice_bundle["context"]["build_id"][:12])
        page.locator("#edit").click()
        exact="Мои правки.\n\n**Акцент** и ~~правка~~. 🐌"
        page.locator("#editor").fill(exact)
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event:page.locator("#save-session").click()
        saved=tmp_path/"session.json";event.value.save_as(saved)
        value=json.loads(saved.read_text(encoding="utf-8"))
        assert value["voice_bundle"]==voice_bundle and value["drafts"][0]["markdown"]==exact
        page.reload();page.locator("#open-session").set_input_files(saved)
        expect(page.locator("#editor")).to_have_value(exact)
        expect(page.locator("#language")).to_have_value("ru")
        expect(page.locator("#style")).to_have_value("voice")
        bad=tmp_path/"bad.json";bad.write_text('{"schema_version":"unsupported"}',encoding="utf-8")
        page.locator("#voice-file").set_input_files(bad)
        expect(page.locator("#error")).to_be_visible()
        expect(page.locator("#editor")).to_have_value(exact)
        expect(page.locator("#voice-status")).to_contain_text(voice_bundle["context"]["build_id"][:12])
        assert len(calls)==1 and calls[0]["voice_reference"]==""
        browser.close()
