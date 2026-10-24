"""Real original synthetic fixtures, including an MP4 with audio and captions."""
import shutil
from pathlib import Path

import pytest

from patchpitch import editorial as e, editorial_render as rendering, editorial_media as media
from patchpitch.run_store import RunError
from test_editorial import workspace, complete, patch

FIXTURES = Path(__file__).parent / "fixtures"


def with_media(root):
    complete(root)
    for identity, name, alt in [("screen", "editorial-image.png", "A synthetic green screen"),
                                ("motion", "editorial-motion.gif", "A synthetic moving test pattern"),
                                ("demo", "editorial-tone.mp4", ""), ("captions", "editorial-subtitles.vtt", "")]:
        patch(root, [{"type": "import_media", "id": identity, "path": str(FIXTURES / name), "alt": alt,
                      "provenance": "Original synthetic test fixture generated for PatchPitch"}])
    patch(root, [{"type": "asset", "id": "demo", "value": {"poster_id": "screen", "subtitle_id": "captions"}}])
    doc = e.load(root)[2]
    section = doc.sections[0].model_dump()
    for identity in ["screen", "motion", "demo"]:
        section["blocks"].append({"id": "B-" + identity, "kind": "media", "asset_id": identity})
    patch(root, [{"type": "section", "value": section}, {"type": "metadata", "value": {"cover_asset_id": "screen"}}])


def test_real_assets_portable_preview_and_dev_fallback(workspace, tmp_path):
    with_media(workspace)
    doc = e.load(workspace)[2]
    video = next(a for a in doc.assets if a.id == "demo")
    assert video.audio_present is True and video.duration_seconds == 2.0
    image = next(a for a in doc.assets if a.id == "screen")
    assert (image.width, image.height) == (160, 90)
    before = e.status(workspace)
    assert not before["media_ready_for_dev"] and "MEDIA_UNRESOLVED:demo" in before["media_blockers"]
    moved = tmp_path / "moved"
    shutil.copytree(workspace, moved)
    out = tmp_path / "preview"
    rendering.export(moved, out)
    html = (out / "preview.html").read_text(encoding="utf-8")
    assert "<video controls" in html and "<track" in html and "muted" not in html and "autoplay" not in html
    assert "<img" in html and "<figcaption>" not in html
    assert str(workspace) not in html and "private" not in html
    for asset in doc.assets:
        assert (out / asset.path).read_bytes() == (moved / asset.path).read_bytes()
    for asset in doc.assets:
        patch(moved, [{"type": "asset", "id": asset.id, "value": {"public_url": "https://example.com/media/" + asset.id}}])
    out2 = tmp_path / "public-export"
    rendering.export(moved, out2)
    body = (out2 / "article.md").read_text(encoding="utf-8")
    assert "https://example.com/media/demo" in body and "<video" not in body
    assert e.status(moved)["media_ready_for_dev"]


@pytest.mark.parametrize("url", ["http://example.com/a", "https://localhost/a", "https://127.0.0.1/a", "https://[::1]/a", "https://192.168.1.1/a", "https://user:pass@example.com/a", "file:///secret", "javascript:alert(1)"])
def test_public_url_rejects_private_and_executable_destinations(url):
    with pytest.raises(RunError):
        media.https_url(url)


def test_content_change_and_traversal_never_export(workspace, tmp_path):
    with_media(workspace)
    root, manifest, doc, inputs = e.load(workspace)
    with pytest.raises(RunError):
        e.inside(root, "../outside")
    (root / doc.assets[0].path).write_bytes(b"changed")
    with pytest.raises(RunError) as exc:
        rendering.export(root, tmp_path / "export")
    assert exc.value.code == "MEDIA_INVALID"


def test_wrong_signature_and_missing_alt(workspace, tmp_path):
    complete(workspace)
    fake = tmp_path / "fake.png"
    fake.write_text("<script>alert(1)</script>", encoding="utf-8")
    with pytest.raises(RunError) as exc:
        patch(workspace, [{"type": "import_media", "id": "fake", "path": str(fake), "provenance": "synthetic"}])
    assert exc.value.code == "MEDIA_TYPE"
    patch(workspace, [{"type": "import_media", "id": "screen", "path": str(FIXTURES / "editorial-image.png"), "provenance": "synthetic"}])
    patch(workspace, [{"type": "metadata", "value": {"cover_asset_id": "screen"}}])
    assert "MEDIA_ALT_REQUIRED:screen" in e.status(workspace)["blockers"]


def test_private_dns_result_is_rejected_before_connection(monkeypatch):
    monkeypatch.setattr(media.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.0.0.1", 443))])
    with pytest.raises(RunError) as exc:
        media.public_fetch("https://example.com/asset")
    assert exc.value.code == "PUBLIC_URL_PRIVATE"
