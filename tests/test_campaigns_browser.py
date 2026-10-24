"""Browser MOCK checks for new six-tag flow and CLI session restoration."""
import json

from playwright.sync_api import sync_playwright, expect

from test_browser import ui_url
from test_campaigns import catalog_data, job_files, transport
from patchpitch import campaigns, social
from patchpitch.campaign_export import export_session
from patchpitch.models import SocialInput


def test_six_tags_default_and_edited_export_guard(ui_url, transport):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(permissions=["clipboard-read", "clipboard-write"])
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/health", lambda r: r.fulfill(json={"ollama": "ready", "model": "TEST_ONLY"}))
        page.route("**/api/social", lambda r: r.fulfill(json=social.generate(SocialInput.model_validate(r.request.post_data_json))))
        page.goto(ui_url)
        page.locator("#product").fill("PatchPitch")
        page.locator("#description").fill("Prepare local drafts from selected facts.")
        page.locator("#audience").fill("developers")
        page.locator("#changes").fill("PatchPitch prepares local drafts from selected facts.")
        page.locator("#format").select_option("x_single")
        page.locator("#x-tags-tools > summary").click()
        assert not page.locator("#legacy-x").is_checked()
        page.locator("#x-catalog").set_input_files({"name": "synthetic.json", "mimeType": "application/json", "buffer": json.dumps(catalog_data()).encode()})
        expect(page.locator("#x-catalog-status")).to_contain_text("synthetic-test-only")
        page.locator("#confirmed").check()
        page.locator("#generate").click()
        expect(page.locator(".social-card")).to_have_count(1)
        text = page.locator("#text-P01").input_value()
        assert text.count("#") == 6 and len(transport) == 2
        page.get_by_role("button", name="Copy this post", exact=True).click()
        expect(page.locator("#status")).to_contain_text("Copied")
        page.locator("#text-P01").fill(text.replace("#LocalAI", ""))
        page.get_by_role("button", name="Copy this post", exact=True).click()
        expect(page.locator("#error")).to_contain_text("exactly six")
        assert not errors
        browser.close()


def test_cli_session_restores_four_formats_without_inference(ui_url, job_files, transport):
    job, out, _ = job_files
    assert campaigns.run(job, out)[1] == 0
    (out / "outputs/telegram/draft.md").write_text("Keep the exact edited CLI text.\n", encoding="utf-8")
    export_session(out, out / "session.json")
    count = len(transport)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/health", lambda r: r.fulfill(json={"ollama": "ready", "model": "TEST_ONLY"}))
        page.goto(ui_url)
        page.locator("#session-tools > summary").click()
        page.locator("#open-session").set_input_files(str(out / "session.json"))
        expect(page.locator("#status")).to_contain_text("Session opened")
        expect(page.locator("#editor")).to_have_value("Keep the exact edited CLI text.\n")
        for label in ["Telegram post", "DEV article", "GitHub release notes", "X Single"]:
            page.locator("#saved-drafts").get_by_role("button", name=label, exact=True).click()
            expect(page.locator("#output-preset")).to_contain_text(label)
        expect(page.locator("#text-P01")).to_have_value((out / "outputs/x/P01.txt").read_text().removesuffix("\n"))
        assert len(transport) == count and not errors
        browser.close()
