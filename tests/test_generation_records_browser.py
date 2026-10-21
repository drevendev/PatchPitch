"""MOCK browser acceptance of the normal app's record/retry workflow."""
import json

from playwright.sync_api import sync_playwright, expect

from test_browser import ui_url
from patchpitch import generator
from patchpitch.models import PitchInput


def test_rejection_keeps_edits_and_record_survives_successful_retry(ui_url, input_data, monkeypatch, tmp_path):
    calls = []
    rejected = {"done": True, "model": "MOCK", "message": {"content": json.dumps({
        "text": '<img src=x onerror="window.xss=1"> C01: Rejected prose.',
        "source_ids": ["C01"], "hashtags": []})}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        page.route("**/static/example.json", lambda r: r.fulfill(json=input_data))

        def attempt(route):
            body = route.request.post_data_json
            calls.append(body)
            raw = rejected if len(calls) == 2 else {"done": True, "model": "MOCK", "message": {"content": json.dumps({
                "text": f"Find notes by title. Draft {len(calls)}.", "source_ids": ["C01"], "hashtags": []})}}
            monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: raw)
            try:
                result = generator.generate(PitchInput.model_validate(body))
                route.fulfill(json=result)
            except generator.GenerationError as exc:
                route.fulfill(status=exc.status, json={"error": {"code": exc.code, "message": exc.message}, "evidence": exc.evidence})

        page.route("**/api/pitch", attempt)
        page.goto(ui_url)
        page.locator("#example").click()
        page.locator("#format").select_option("community")
        page.locator("#confirmed").check()
        page.locator("#generate").click()
        page.locator("#result").wait_for(state="visible")
        page.locator("#edit").click()
        manual = "My carefully edited words.\n"
        page.locator("#editor").fill(manual)
        page.once("dialog", lambda d: d.accept())
        page.locator("#generate").click()
        expect(page.locator("#error")).to_contain_text("source IDs or hashtags")
        assert page.locator("#editor").input_value() == manual
        assert page.locator("#product").input_value() == input_data["product"]["name"]
        expect(page.locator("#editor")).to_be_enabled()
        assert page.locator("#record-raw img").count() == 0
        assert page.locator("#record-raw").inner_text() == rejected["message"]["content"]
        assert page.evaluate("window.xss") is None
        page.locator("#copy").click()
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n") == manual
        page.locator("#copy-record").click()
        record = json.loads(page.evaluate("navigator.clipboard.readText()"))
        assert record["status"] == "failed" and record["evidence"]["raw_response"] == rejected
        assert record["input_snapshot"] == calls[1] and record["response"] is None
        with page.expect_download() as download:
            page.locator("#download").click()
        final_path = tmp_path / "preserved.md"
        download.value.save_as(final_path)
        assert final_path.read_text(encoding="utf-8") == manual
        page.once("dialog", lambda d: d.accept())
        page.locator("#generate").click()
        expect(page.locator("#draft-view")).to_contain_text("Draft 3.")
        expect(page.locator("#error")).to_be_hidden()
        assert len(calls) == 3
        page.locator("#record-choice").select_option("A02")
        page.locator("#product").fill("Different pending input")
        page.locator("#copy-record").click()
        retained = json.loads(page.evaluate("navigator.clipboard.readText()"))
        assert retained == record
        with page.expect_download() as download:
            page.locator("#download-record").click()
        assert download.value.suggested_filename.endswith("-A02-failed.json")
        saved = tmp_path / "failed.json"
        download.value.save_as(saved)
        assert json.loads(saved.read_text(encoding="utf-8")) == record
        page.locator("#record-choice").select_option("A03")
        page.locator("#copy-record").click()
        accepted = json.loads(page.evaluate("navigator.clipboard.readText()"))
        assert accepted["review_snapshot"]["markdown"] == accepted["response"]["markdown"]
        assert accepted["input_snapshot"]["product"]["name"] != "Different pending input"
        browser.close()


def test_unavailable_model_has_no_invented_response_or_identity(ui_url, input_data):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        page.route("**/static/example.json", lambda r: r.fulfill(json=input_data))
        page.route("**/api/pitch", lambda r: r.fulfill(status=504, json={"error": {"code": "timeout", "message": "Timed out."},
            "evidence": {"raw_response": None, "returned_model": None, "configured_model": "CONFIGURED_ONLY", "elapsed_seconds": 2.5}}))
        page.goto(ui_url)
        page.locator("#example").click()
        page.locator("#confirmed").check()
        page.locator("#generate").click()
        expect(page.locator("#record-raw")).to_have_text("No model response was available for this attempt.")
        assert "returned model: unknown" in page.locator("#record-summary").inner_text()
        assert page.locator("#result").is_hidden()
        assert page.locator("#product").input_value() == input_data["product"]["name"]
        page.locator("#copy-record").click()
        record = json.loads(page.evaluate("navigator.clipboard.readText()"))
        assert record["error"]["code"] == "timeout" and record["evidence"]["raw_response"] is None
        browser.close()
