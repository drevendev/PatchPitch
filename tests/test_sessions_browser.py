"""Real browser and local API, MOCK inference. No automatic persistence."""
import json

from playwright.sync_api import expect, sync_playwright

from test_browser import ui_url
from test_social_browser import load_and_select, open_page, result_for
from patchpitch import generator
from patchpitch.models import PitchInput


def test_context_review_media_reset_and_draft_identity(ui_url, monkeypatch):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = open_page(browser, ui_url)
        page.on("dialog", lambda d: d.accept())
        bodies = []
        def answer(route):
            body = route.request.post_data_json; bodies.append(body)
            route.fulfill(json=result_for(body, monkeypatch))
        page.route("**/api/social", answer)
        load_and_select(page, "x_single")
        page.locator("#audience").fill("Other indie makers")
        expect(page.locator("#confirmed")).not_to_be_checked()
        expect(page.locator("#pack-status")).to_contain_text("Derived context")
        page.locator("#confirmed").check(); page.locator("#generate").click()
        expect(page.locator(".social-card")).to_have_count(1)
        assert bodies[-1]["context_overrides"] == ["audience"]
        page.locator("#release").fill("Another update"); page.locator("#confirmed").check(); page.locator("#generate").click()
        expect(page.locator("#output-preset")).to_contain_text("Another update")
        assert len(set(page.locator("#saved-drafts button").all_text_contents())) == 2
        page.locator("#writing-options > summary").click(); page.locator("#media-note").fill("Old screenshot")
        page.locator("#fact-pack").select_option("idle-fantasy-shop"); page.locator("#load-pack").click()
        expect(page.locator("#product")).to_have_value("Idle Fantasy Shop")
        expect(page.locator("#media-note")).to_have_value("")
        browser.close()


def test_session_roundtrip_and_invalid_file_preserve_exact_edits(ui_url, tmp_path, monkeypatch):
    calls = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = open_page(browser, ui_url)
        page.on("dialog", lambda d: d.accept())
        def answer(route):
            body = route.request.post_data_json; calls.append(body)
            route.fulfill(json=result_for(body, monkeypatch))
        page.route("**/api/social", answer)
        load_and_select(page); page.locator("#generate").click()
        expect(page.locator(".social-card")).to_have_count(5)
        text = "Мои точные правки: <script>literal</script> e\u0301.\nSecond line."
        page.locator("#text-P03").fill(text); page.locator("#media-P03").fill("Screenshot note")
        page.locator('[data-post-id="P03"]').get_by_role("button", name="Move up", exact=True).click()
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event: page.locator("#save-session").click()
        saved = tmp_path/"session.json"; event.value.save_as(saved)
        original = json.loads(saved.read_text(encoding="utf-8"))
        page.reload(); expect(page.locator("#product")).to_have_value("")
        page.locator("#open-session").set_input_files(saved)
        expect(page.locator("#text-P03")).to_have_value(text)
        assert page.locator(".social-card").nth(1).get_attribute("data-post-id") == "P03"
        expect(page.locator("#media-P03")).to_have_value("Screenshot note")
        expect(page.locator("#confirmed")).not_to_be_checked()
        assert page.locator("#record-choice option").count() == 1 and len(calls) == 1
        assert page.evaluate("generationRecordExport()")
        invalid = tmp_path/"invalid.json"; invalid.write_text(json.dumps({**original, "schema_version": 99}), encoding="utf-8")
        page.locator("#open-session").set_input_files(invalid)
        expect(page.locator("#error")).to_be_visible()
        expect(page.locator("#text-P03")).to_have_value(text)
        assert len(calls) == 1
        browser.close()


def test_rewrite_refreshes_current_sources_and_labels_old_warnings(ui_url, monkeypatch):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = open_page(browser, ui_url)
        page.on("dialog", lambda d: d.accept())
        def answer(route):
            body = route.request.post_data_json
            data = result_for(body, monkeypatch)
            if body.get("operation") == "regenerate":
                data["draft"]["posts"][0]["source_ids"] = ["C01"]
                data["warnings"] = []
            else: data["warnings"].append("Old warning from initial generation")
            route.fulfill(json=data)
        page.route("**/api/social", answer)
        load_and_select(page); page.locator("#generate").click()
        expect(page.locator(".social-card")).to_have_count(5)
        page.locator("#text-P03").fill("Keep this other edit.")
        page.locator('[data-post-id="P01"]').get_by_role("button", name="Regenerate this post", exact=True).click()
        expect(page.locator("#text-P01")).to_be_enabled()
        assert page.evaluate("result.source_map[0].source_ids") == ["C01"]
        assert "C01" not in page.evaluate("result.omitted_source_ids")
        warning = page.locator("#warnings").inner_text()
        assert "Original generation (historical): Old warning" in warning
        current = [p for p in page.locator("#warnings p").all_text_contents() if p.startswith("Selected sources not referenced:")]
        assert len(current) == 1 and "C01" not in current[0]
        expect(page.locator("#text-P03")).to_have_value("Keep this other edit.")
        assert page.evaluate("generationRecords[0].response.source_map[0].source_ids") == ["C03"]
        browser.close()


def test_session_restores_multiple_formats_and_immutable_failed_record(ui_url, monkeypatch, tmp_path):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = open_page(browser, ui_url)
        page.on("dialog", lambda d: d.accept())
        page.route("**/api/social", lambda route: route.fulfill(json=result_for(route.request.post_data_json, monkeypatch)))
        legacy_calls = []
        def legacy(route):
            body = route.request.post_data_json; legacy_calls.append(body)
            if len(legacy_calls) == 2:
                route.fulfill(status=502, json={"error": {"code": "invalid_draft", "message": "MOCK rejected response"},
                    "evidence": {"raw_response": {"message": {"content": "Original rejected output"}}}})
                return
            monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: {"done": True, "model": "MOCK", "message": {"content": json.dumps({
                "text": "PatchPitch keeps selected notes available for review.", "source_ids": ["C03"], "hashtags": []})}})
            route.fulfill(json=generator.generate(PitchInput.model_validate(body)))
        page.route("**/api/pitch", legacy)
        load_and_select(page); page.locator("#generate").click(); expect(page.locator(".social-card")).to_have_count(5)
        page.locator("#text-P02").fill("Keep the thread edit.")
        page.locator("#format").select_option("x_single"); page.locator("#generate").click(); expect(page.locator(".social-card")).to_have_count(1)
        page.locator("#text-P01").fill("Keep the single edit.")
        page.locator("#format").select_option("community"); page.locator("#generate").click()
        expect(page.locator("#draft-view")).to_be_visible()
        page.locator("#edit").click(); page.locator("#editor").fill("Точные ручные правки.\n\nNo automatic revalidation.\n")
        page.locator("#generate").click(); expect(page.locator("#error")).to_contain_text("MOCK rejected")
        before = page.evaluate("sessionSnapshot()")
        assert before["records"][-1]["status"] == "failed"
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event: page.locator("#save-session").click()
        saved = tmp_path/"multi-session.json"; event.value.save_as(saved)
        page.reload(); page.locator("#open-session").set_input_files(saved)
        expect(page.locator("#editor")).to_be_visible()
        after = page.evaluate("sessionSnapshot()")
        assert after["drafts"] == before["drafts"]
        assert after["records"] == before["records"]
        assert page.locator("#record-choice option").count() == 4
        assert page.locator("#record-raw").text_content() == "Original rejected output"
        assert len(legacy_calls) == 2
        browser.close()


def test_validation_failure_can_be_saved_and_restored(ui_url, monkeypatch, tmp_path):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); page = open_page(browser, ui_url)
        page.on("dialog", lambda d: d.accept())
        page.route("**/api/social", lambda route: route.fulfill(status=422,
            json={"detail": "Input was rejected before inference"}))
        load_and_select(page, "x_single")
        # Whitespace satisfies browser required validation but fails the API model.
        page.locator("#product").fill("   "); page.locator("#confirmed").check()
        page.locator("#generate").click()
        expect(page.locator("#record-outcome")).to_contain_text("Failed")
        original = page.evaluate("structuredClone(generationRecords)")
        page.locator("#session-tools > summary").click()
        with page.expect_download() as event: page.locator("#save-session").click()
        saved = tmp_path/"rejected-input.json"; event.value.save_as(saved)
        page.reload(); page.locator("#open-session").set_input_files(saved)
        expect(page.locator("#record-outcome")).to_contain_text("Failed")
        assert page.evaluate("generationRecords") == original
        expect(page.locator("#product")).to_have_value("   ")
        browser.close()
