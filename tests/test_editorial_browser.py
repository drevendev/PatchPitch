"""Real Chromium/CSP/local files; inference remains explicitly MOCK."""
from playwright.sync_api import sync_playwright, expect

from patchpitch import editorial as e
from patchpitch.editorial_api import dispatch
from test_browser import ui_url
from test_editorial import workspace, model, complete
from test_editorial_media import with_media


def test_editorial_ui_edits_one_section_and_plays_real_media(ui_url, workspace):
    with_media(workspace)
    original = e.load(workspace)[2].sections[1].model_dump()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(ui_url + "/editorial")
        page.locator("#work").fill(str(workspace))
        page.locator("#open").click()
        expect(page.locator("#workspace")).to_be_visible()
        page.locator("#block-B01").fill("I keep my exact local words.")
        page.locator('[data-section="S01"]').get_by_role("button", name="Save this section", exact=True).click()
        expect(page.locator("#state")).to_contain_text("ARTICLE_NOT_REVIEWED")
        expect(page.locator("#block-B01")).to_have_value("I keep my exact local words.")
        assert e.load(workspace)[2].sections[1].model_dump() == original
        page.locator("#build-preview").click()
        expect(page.locator("#preview-link")).to_be_visible()
        preview = browser.new_page()
        response = preview.goto(ui_url + page.locator("#preview-link").get_attribute("href"))
        assert "unsafe-eval" not in response.headers["content-security-policy"]
        expect(preview.locator("h1")).to_have_text("My local drafts")
        expect(preview.get_by_text("I keep my exact local words.", exact=True)).to_be_visible()
        video = preview.locator("video")
        expect(video).to_have_attribute("controls", "")
        video.scroll_into_view_if_needed()
        video.click()
        video.evaluate("v => {v.muted=false;v.volume=0.2;return v.play()}")
        expect(video).to_have_js_property("muted", False)
        expect(video).to_have_js_property("paused", False)
        assert video.evaluate("v => v.duration") == 2
        video.evaluate("v => {v.pause();v.currentTime=1}")
        expect(video).to_have_js_property("currentTime", 1)
        expect(video.locator("track")).to_have_count(1)
        preview.locator("#width").click()
        expect(preview.locator("main")).to_have_class("mobile")
        assert not errors
        browser.close()


def test_editorial_ui_uses_shared_candidate_acceptance(ui_url, workspace, model):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        def model_route(route):
            body = route.request.post_data_json
            if body["action"] in {"outline", "draft", "revise", "x"}:
                route.fulfill(json=dispatch(body))
            else:
                route.continue_()
        page.route("**/api/editorial", model_route)
        page.goto(ui_url + "/editorial")
        page.locator("#work").fill(str(workspace)); page.locator("#open").click()
        expect(page.locator("#workspace")).to_be_visible()
        page.locator("#review-sources").click()
        page.locator("#outline").click()
        expect(page.locator(".candidate")).to_have_count(1)
        page.get_by_role("button", name="Accept this candidate", exact=True).click()
        expect(page.locator("#plan-title")).to_have_value("My local drafts")
        page.get_by_role("button", name="I reviewed this plan", exact=True).click()
        page.locator("#draft").click()
        expect(page.locator("#message")).to_contain_text("Proposal saved")
        candidates = page.locator(".candidate").filter(has=page.get_by_role("heading", name="draft ·", exact=False))
        expect(candidates).to_have_count(1)
        candidates.get_by_role("button", name="Accept this candidate", exact=True).click()
        expect(page.locator('[data-section="S01"] textarea').first).to_have_value("I keep local drafts.")
        assert len(model) == 3
        browser.close()
