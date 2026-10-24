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
        page.locator(".candidate details summary").click()
        expect(page.locator(".candidate details pre")).to_contain_text('"source_ids"')
        expect(page.locator(".candidate details pre")).to_contain_text('"C01"')
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


def test_saving_one_section_retains_other_unsaved_edits(ui_url, workspace):
    complete(workspace)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(ui_url + "/editorial")
        page.locator("#work").fill(str(workspace)); page.locator("#open").click()
        expect(page.locator("#block-B01")).to_be_visible()
        page.locator("#block-B02").fill("My unsaved second section stays here.")
        page.locator("#block-B01").fill("My saved first section.")
        page.locator('[data-section="S01"]').get_by_role("button", name="Save this section", exact=True).click()
        expect(page.locator("#block-B02")).to_have_value("My unsaved second section stays here.")
        assert e.load(workspace)[2].sections[1].blocks[0].text == "My local edits survive failure."
        page.locator("#build-preview").click()
        expect(page.locator("#error")).to_contain_text("Save pending")
        page.reload()
        page.locator("#open").click()
        expect(page.locator("#block-B02")).to_have_value("My unsaved second section stays here.")
        page.locator('[data-section="S02"]').get_by_role("button", name="Save this section", exact=True).click()
        expect(page.locator("#block-B02")).to_have_value("My unsaved second section stays here.")
        assert e.load(workspace)[2].sections[0].blocks[0].text == "My saved first section."
        browser.close()


def test_switching_workspace_clears_previous_preview_and_x_cards(ui_url, workspace, model):
    from patchpitch import editorial_generation as writing
    complete(workspace)
    result = writing.propose(workspace, "x", "first-workspace-series")
    writing.accept(workspace, result["candidate"], result["revision_id"])
    second = workspace.parent / "second-workspace"
    e.initialize(workspace.parent / "editorial.json", second)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(ui_url + "/editorial")
        page.locator("#work").fill(str(workspace)); page.locator("#open").click()
        expect(page.locator("#x-posts .section-card")).to_have_count(3)
        page.locator("#x-edit-P02").fill("My unsaved second announcement")
        page.reload(); page.locator("#open").click()
        expect(page.locator("#x-edit-P02")).to_have_value("My unsaved second announcement")
        page.locator("#discard-buffer").click()
        expect(page.locator("#x-edit-P02")).not_to_have_value("My unsaved second announcement")
        page.locator("#build-preview").click()
        expect(page.locator("#preview-link")).to_be_visible()
        page.locator("#work").fill(str(second)); page.locator("#open").click()
        expect(page.locator("#state")).to_contain_text("sources_ready")
        expect(page.locator("#x-posts .section-card")).to_have_count(0)
        expect(page.locator("#preview-link")).to_be_hidden()
        browser.close()
