"""A small, escaped block renderer shared by CLI and studio. No raw HTML/Liquid."""
import html
import re
from pathlib import Path
from urllib.parse import urlsplit

from .run_store import RunError, digest, write_json, write_text, write_bytes


CSS = """html{color-scheme:light}body{margin:0;background:#f4f3ef;color:#20252b;font:18px/1.75 system-ui,sans-serif}main{max-width:780px;margin:40px auto;padding:32px;background:white;border-radius:16px}h1{font-size:2.5rem;line-height:1.15}h2{line-height:1.25;margin-top:2em}img,video{max-width:100%;height:auto}video{width:100%}pre{overflow:auto;background:#17222b;color:#f3f5f7;padding:20px;border-radius:8px}code{font-size:.9em}figure{margin:28px 0}figcaption,.meta,.notice{font-size:.85em;color:#56616b}.placeholder{border:1px dashed #7c8791;padding:20px}.toolbar{display:flex;gap:12px;align-items:center}.mobile{max-width:375px}button{font:inherit}a{color:#17518b}blockquote{border-left:3px solid #aaa;padding-left:16px}@media(max-width:700px){main{margin:0;padding:20px;border-radius:0}h1{font-size:2rem}}"""
JS = '"use strict";document.getElementById("width").addEventListener("click",()=>document.querySelector("main").classList.toggle("mobile"));'
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"


def safe_link(value):
    try:
        url = urlsplit(value)
        return url.scheme in {"https", "http"} and bool(url.hostname) and not url.username and not url.password and not any(ord(c) < 32 for c in value)
    except ValueError:
        return False


def inline(text):
    """Deliberately limited Markdown: code, emphasis and ordinary links, escaped first."""
    pattern = r"(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[[^\]\n]+\]\([^\s)]+\))"
    parts = []
    for token in re.split(pattern, text):
        if token.startswith("`") and token.endswith("`"):
            parts.append("<code>" + html.escape(token[1:-1]) + "</code>")
        elif token.startswith("**") and token.endswith("**"):
            parts.append("<strong>" + html.escape(token[2:-2]) + "</strong>")
        elif token.startswith("*") and token.endswith("*"):
            parts.append("<em>" + html.escape(token[1:-1]) + "</em>")
        else:
            link = re.fullmatch(r"\[([^\]\n]+)\]\(([^\s)]+)\)", token)
            if link and safe_link(link[2]):
                parts.append('<a rel="noreferrer noopener" href="' + html.escape(link[2], quote=True) + '">' + html.escape(link[1]) + "</a>")
            else:
                parts.append(html.escape(token))
    return "".join(parts).replace("\n", "<br>")


def markdown_escape(text):
    return re.sub(r"([\\\[\]()*_`<>])", r"\\\1", text).replace("\r", " ").replace("\n", " ")


def media_markdown(asset, assets, public):
    url = asset.public_url if public else asset.path
    url = url or ("UNRESOLVED-" + asset.id)
    caption = markdown_escape(asset.caption)
    if asset.kind in {"image", "gif"}:
        text = f"![{markdown_escape(asset.alt)}](<{url}>)"
    elif asset.kind == "video":
        poster = assets.get(asset.poster_id)
        if poster:
            poster_url = (poster.public_url if public else poster.path) or "UNRESOLVED-" + poster.id
            text = f"[![{markdown_escape(poster.alt or 'Watch video')}](<{poster_url}>)](<{url}>)"
        else:
            text = f"[Watch video — external player](<{url}>)"
    else:
        text = f"[Subtitles](<{url}>)"
    return text + ("\n\n" + caption if caption else "")


def body_markdown(doc, inputs, public=True):
    parts = []
    assets = {a.id: a for a in doc.assets}
    for section in doc.sections:
        parts.append("## " + section.heading)
        for block in section.blocks:
            if block.kind == "paragraph":
                parts.append(block.text)
            elif block.kind == "list":
                parts.append("\n".join("- " + text for text in block.items))
            elif block.kind == "code":
                parts.append(inputs["snippets"][block.snippet_id]["text"])
            elif block.kind == "media" and block.asset_id in assets:
                parts.append(media_markdown(assets[block.asset_id], assets, public))
    cta = inputs["sources"].get("cta_text", "")
    if cta:
        parts.append(cta)
    return "\n\n".join(parts) + "\n"


def render_media(asset, assets, dev=False):
    esc = lambda value: html.escape(value, quote=True)
    if dev:
        if not asset.public_url:
            return '<div class="placeholder">Unresolved public media: ' + esc(asset.id) + "</div>"
        # No external content is loaded by simply viewing a local preview.
        return '<div class="placeholder">DEV media: ' + esc(asset.id) + ' · <a rel="noreferrer noopener" href="' + esc(asset.public_url) + '">Open public ' + ("external video player" if asset.kind == "video" else "asset") + "</a></div>"
    if asset.kind in {"image", "gif"}:
        return '<img src="' + esc(asset.path) + '" alt="' + esc(asset.alt) + '" loading="lazy">'
    if asset.kind == "video":
        poster = assets.get(asset.poster_id)
        subtitle = assets.get(asset.subtitle_id)
        attrs = ' controls preload="metadata" playsinline'
        if poster:
            attrs += ' poster="' + esc(poster.path) + '"'
        track = '<track kind="subtitles" label="Subtitles" src="' + esc(subtitle.path) + '">' if subtitle else ""
        return '<video' + attrs + '><source src="' + esc(asset.path) + '" type="video/mp4">' + track + "Your browser cannot play this video.</video>"
    return '<a href="' + esc(asset.path) + '">Subtitles</a>'


def html_document(doc, inputs, dev=False):
    assets = {a.id: a for a in doc.assets}
    content = []
    cover = assets.get(doc.metadata.cover_asset_id)
    if cover:
        content.append(render_media(cover, assets, dev))
    content.append("<h1>" + html.escape(doc.metadata.title) + "</h1>")
    content.append('<p class="meta">' + html.escape(doc.metadata.description) + "</p>")
    content.append('<p class="meta">' + html.escape(" · ".join(doc.metadata.tags)) + "</p>")
    for section in doc.sections:
        content.append('<section id="' + html.escape(section.id, quote=True) + '"><h2>' + html.escape(section.heading) + "</h2>")
        for block in section.blocks:
            if block.kind == "paragraph":
                content.append("<p>" + inline(block.text) + "</p>")
            elif block.kind == "list":
                content.append("<ul>" + "".join("<li>" + inline(t) + "</li>" for t in block.items) + "</ul>")
            elif block.kind == "code":
                code = inputs["snippets"][block.snippet_id]["text"]
                code = re.sub(r"^```[^\n]*\n", "", code).removesuffix("```")
                content.append("<pre><code>" + html.escape(code) + "</code></pre>")
            elif block.kind == "media":
                asset = assets[block.asset_id]
                content.append("<figure>" + render_media(asset, assets, dev) + ("<figcaption>" + inline(asset.caption) + "</figcaption>" if asset.caption else "") + "</figure>")
        content.append("</section>")
    if inputs["sources"].get("cta_text"):
        content.append("<p>" + inline(inputs["sources"]["cta_text"]) + "</p>")
    notice = "DEV export approximation: public assets are links; inspect the actual DEV draft separately." if dev else "Local article preview: video playback here does not establish support for inline video on DEV."
    return '<!doctype html><html lang="' + doc.language + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="' + html.escape(CSP, quote=True) + '"><title>' + html.escape(doc.metadata.title) + '</title><link rel="stylesheet" href="preview.css"><script src="preview.js" defer></script></head><body><main><nav class="toolbar"><button id="width" type="button">Desktop / mobile</button><a href="' + ("preview.html" if dev else "dev-preview.html") + '">' + ("Local media" if dev else "DEV export") + '</a></nav><p class="notice">' + notice + '</p>' + "".join(content) + '<footer class="meta">Revision ' + html.escape(doc.revision_id) + "</footer></main></body></html>"


def export(work, out):
    from .editorial import load, inside, check_document
    from .editorial_media import media_errors
    from .editorial_x import export_series
    root, manifest, doc, inputs = load(work)
    check_document(doc, inputs)
    errors = media_errors(root, doc)
    if errors:
        raise RunError("MEDIA_INVALID", "; ".join(errors), 4)
    destination = Path(out).resolve()
    if destination.is_relative_to(root / "inputs") or destination == root or destination.is_relative_to(root / "media"):
        raise RunError("EXPORT_PATH", "Export to a separate folder, never over workspace inputs/media.")
    existing = destination / "export.json"
    if destination.exists() and any(destination.iterdir()) and not existing.exists():
        raise RunError("OUTPUT_NOT_EMPTY", "Choose an empty preview/export folder.")
    if existing.exists():
        from .run_store import read_json
        old = read_json(existing)
        if old.get("document_id") != doc.document_id:
            raise RunError("OUTPUT_NOT_EMPTY", "This export belongs to another document.")
        # Do not silently erase manually changed exported files.
        for name, expected in old.get("files", {}).items():
            path = inside(destination, name)
            import hashlib
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RunError("EXPORT_CHANGED", "Exported files were edited. Import the edits or choose a new export folder.", 4)
    destination.mkdir(parents=True, exist_ok=True)
    files = {}
    def save(name, raw):
        import hashlib
        target = inside(destination, name, exists=False)
        write_bytes(target, raw)
        files[name] = hashlib.sha256(raw).hexdigest()
    save("preview.css", CSS.encode())
    save("preview.js", JS.encode())
    save("preview.html", html_document(doc, inputs).encode())
    save("dev-preview.html", html_document(doc, inputs, dev=True).encode())
    save("article.md", body_markdown(doc, inputs, public=True).encode())
    import json
    save("article.json", json.dumps(doc.metadata.model_dump(), ensure_ascii=False, indent=2).encode())
    # Public manifest excludes private source paths/provenance and unused private assets.
    from .editorial_media import used_assets
    assets = []
    for a in doc.assets:
        if a.id not in used_assets(doc):
            continue
        save(a.path, inside(root, a.path).read_bytes())
        assets.append({k: getattr(a, k) for k in ("id", "kind", "path", "sha256", "alt", "caption", "public_url")})
    save("media-manifest.json", json.dumps({"assets": assets}, ensure_ascii=False, indent=2).encode())
    x = export_series(root, manifest, doc)
    if x.get("status") == "ready":
        for index, post in enumerate(x["posts"], 1):
            save(f"x/{index:02}.txt", (post["text"] + "\n").encode())
        save("x/announcements.md", ("\n\n---\n\n".join(p["text"] for p in x["posts"]) + "\n").encode())
        save("x/manifest.json", json.dumps(x, ensure_ascii=False, indent=2).encode())
    write_json(destination / "export.json", {"schema_version": "patchpitch.editorial-export/v1", "document_id": doc.document_id,
        "revision_id": doc.revision_id, "files": files, "body_sha256": digest(body_markdown(doc, inputs, True)),
        "unresolved_media": media_errors(root, doc, public=True), "x_state": x["status"]})
    return {"status": "exported", "revision_id": doc.revision_id,
            "artifacts": {"preview": str(destination / "preview.html"), "dev_preview": str(destination / "dev-preview.html"), "export": str(destination)}}
