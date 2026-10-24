"""Bounded real assets and explicit HTTPS checks, without media services or codecs."""
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import struct
from pathlib import Path
from urllib.parse import urlsplit, urljoin

from .editorial_models import Asset
from .run_store import RunError


def https_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise ValueError()
        host = parsed.hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError()
        except ValueError:
            if all(c in "0123456789.:" for c in host) or ":" in host:
                raise ValueError()
        if any(ord(c) < 33 for c in value) or "\\" in value:
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise RunError("PUBLIC_URL_INVALID", "Use an ordinary public HTTPS URL without credentials or private addresses.", 4)


def public_fetch(url, method="GET", limit=2_000_000):
    """Resolve once, reject private answers, pin the TLS connection to that address."""
    for _ in range(4):
        parsed = https_url(url)
        connection = None
        try:
            answers = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
            addresses = list(dict.fromkeys(item[4][0] for item in answers))
            if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
                raise RunError("PUBLIC_URL_PRIVATE", "Public checks refuse private or ambiguous DNS destinations.", 4)
            connection = http.client.HTTPSConnection(parsed.hostname, timeout=10)
            sock = socket.create_connection((addresses[0], 443), timeout=10)
            connection.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
            route = parsed.path or "/"
            if parsed.query:
                route += "?" + parsed.query
            connection.request(method, route, headers={"User-Agent": "PatchPitch/0.4 editorial verification", "Accept": "application/json"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.getheader("Location", ""))
                continue
            if response.status != 200:
                raise RunError("PUBLIC_URL_UNAVAILABLE", f"Public resource returned HTTP {response.status}.", 4)
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise RunError("PUBLIC_URL_TOO_LARGE", "Public verification response exceeds its byte budget.", 4)
            return {"url": url, "body": raw, "content_type": response.getheader("Content-Type", "")}
        except (OSError, ValueError, http.client.HTTPException) as exc:
            raise RunError("PUBLIC_URL_UNAVAILABLE", "Cannot verify this public HTTPS resource.", 4) from exc
        finally:
            if connection:
                connection.close()
    raise RunError("PUBLIC_URL_REDIRECTS", "Public verification exceeded its redirect budget.", 4)


def identify(path, head):
    suffix = path.suffix.lower()
    if suffix == ".png" and head.startswith(b"\x89PNG\r\n\x1a\n") and head[12:16] == b"IHDR":
        return "image", "image/png", ".png"
    if suffix in {".jpg", ".jpeg"} and head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg", ".jpg"
    if suffix == ".webp" and head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image", "image/webp", ".webp"
    if suffix == ".gif" and head[:6] in {b"GIF87a", b"GIF89a"}:
        return "gif", "image/gif", ".gif"
    if suffix == ".mp4" and head[4:8] == b"ftyp":
        return "video", "video/mp4", ".mp4"
    if suffix == ".vtt" and head.lstrip(b"\xef\xbb\xbf").startswith(b"WEBVTT"):
        return "subtitle", "text/vtt", ".vtt"
    raise RunError("MEDIA_TYPE", "Use a real PNG/JPEG/WebP/GIF, MP4 or WebVTT file with matching extension.", 4)


def import_asset(root, item, existing):
    from .editorial import parse, inside
    path = Path(item["path"]).resolve()
    if not path.is_file():
        raise RunError("MEDIA_MISSING", "The selected local media file is missing.", 4)
    size = path.stat().st_size
    if not 0 < size <= 200 * 1024 ** 2 or len(existing) >= 30 or sum(a.size for a in existing) + size > 500 * 1024 ** 2:
        raise RunError("MEDIA_BUDGET", "Media count or byte budget exceeded.", 4)
    with path.open("rb") as handle:
        kind, mime, suffix = identify(path, handle.read(64))
    if kind != "video" and size > 20 * 1024 ** 2:
        raise RunError("MEDIA_BUDGET", "Images, GIF and subtitles must fit within 20 MiB.", 4)
    # Bound even if the source grows between stat() and read().
    with path.open("rb") as handle:
        raw = handle.read(size + 1)
    if len(raw) != size:
        raise RunError("MEDIA_CHANGED", "The media file changed while being imported.", 4)
    if kind == "subtitle":
        try:
            raw.decode("utf-8-sig")
        except UnicodeError as exc:
            raise RunError("MEDIA_TYPE", "WebVTT must be UTF-8 text.", 4) from exc
    content_hash = hashlib.sha256(raw).hexdigest()
    relative = f"media/{content_hash}{suffix}"
    asset = parse(Asset, {"id": item["id"], "kind": kind, "path": relative, "sha256": content_hash,
        "size": size, "mime": mime, "alt": item.get("alt", ""), "caption": item.get("caption", ""),
        "decorative": item.get("decorative", False), "provenance": item.get("provenance", ""), **metadata(raw, mime)})
    target = inside(root, relative, exists=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != content_hash:
            raise RunError("MEDIA_CHANGED", "An existing content-addressed asset was modified.", 4)
    else:
        from .run_store import write_bytes
        write_bytes(target, raw)
    return asset


def metadata(raw, mime):
    """Read bounded container metadata, not a decoder or transcoder."""
    result = {}
    try:
        if mime == "image/png":
            result["width"], result["height"] = struct.unpack(">II", raw[16:24])
        elif mime == "image/gif":
            result["width"], result["height"] = struct.unpack("<HH", raw[6:10])
        elif mime == "image/jpeg":
            index = 2
            while index + 4 < len(raw):
                if raw[index] != 255:
                    break
                marker = raw[index + 1]
                size = int.from_bytes(raw[index + 2:index + 4], "big")
                if marker in {0xC0, 0xC1, 0xC2}:
                    result["height"], result["width"] = struct.unpack(">HH", raw[index + 5:index + 9])
                    break
                if size < 2:
                    break
                index += size + 2
        elif mime == "image/webp":
            if raw[12:16] == b"VP8X":
                result["width"] = int.from_bytes(raw[24:27], "little") + 1
                result["height"] = int.from_bytes(raw[27:30], "little") + 1
            elif raw[12:16] == b"VP8 " and raw[23:26] == b"\x9d\x01\x2a":
                result["width"] = int.from_bytes(raw[26:28], "little") & 16383
                result["height"] = int.from_bytes(raw[28:30], "little") & 16383
            elif raw[12:16] == b"VP8L" and raw[20] == 0x2F:
                bits = int.from_bytes(raw[21:25], "little")
                result["width"], result["height"] = (bits & 16383) + 1, ((bits >> 14) & 16383) + 1
        elif mime == "video/mp4":
            found_moov = False
            def boxes(start, end, depth=0):
                nonlocal found_moov
                if depth > 5:
                    return
                index = start
                while index + 8 <= end:
                    size = int.from_bytes(raw[index:index + 4], "big")
                    name, header = raw[index + 4:index + 8], 8
                    if size == 1:
                        size, header = int.from_bytes(raw[index + 8:index + 16], "big"), 16
                    if size == 0:
                        size = end - index
                    if size < header or index + size > end:
                        break
                    data, stop = index + header, index + size
                    if name in {b"moov", b"trak", b"mdia"}:
                        found_moov |= name == b"moov"
                        boxes(data, stop, depth + 1)
                    elif name == b"hdlr" and raw[data + 8:data + 12] == b"soun":
                        result["audio_present"] = True
                    elif name == b"mvhd":
                        offset = 20 if raw[data] == 1 else 12
                        scale = int.from_bytes(raw[data + offset:data + offset + 4], "big")
                        count = 8 if raw[data] == 1 else 4
                        duration = int.from_bytes(raw[data + offset + 4:data + offset + 4 + count], "big")
                        if scale:
                            result["duration_seconds"] = float(duration / scale)
                    index += size
            boxes(0, len(raw))
            if found_moov:
                result.setdefault("audio_present", False)
    except (ValueError, IndexError, struct.error):
        raise RunError("MEDIA_METADATA", "Media container metadata is malformed.", 4)
    if "width" in result and (not 1 <= result["width"] <= 32768 or not 1 <= result["height"] <= 32768 or result["width"] * result["height"] > 64_000_000):
        raise RunError("MEDIA_DIMENSIONS", "Media dimensions exceed the local 64-megapixel budget.", 4)
    return result


def validate_asset(asset, assets):
    if asset.public_url:
        https_url(asset.public_url)
    if asset.poster_id and (asset.poster_id not in assets or assets[asset.poster_id].kind not in {"image", "gif"} or asset.kind != "video"):
        raise RunError("MEDIA_REFERENCE", "A video poster must reference an image.", 4)
    if asset.subtitle_id and (asset.subtitle_id not in assets or assets[asset.subtitle_id].kind != "subtitle" or asset.kind != "video"):
        raise RunError("MEDIA_REFERENCE", "Video subtitles must reference WebVTT.", 4)


def used_assets(doc):
    used = {b.asset_id for s in doc.sections for b in s.blocks if b.kind == "media"}
    if doc.metadata.cover_asset_id:
        used.add(doc.metadata.cover_asset_id)
    for a in doc.assets:
        if a.id in used:
            used.update(v for v in (a.poster_id, a.subtitle_id) if v)
    return used


def media_errors(root, doc, public=False):
    from .editorial import inside
    errors = []
    used = used_assets(doc)
    for asset in doc.assets:
        try:
            path = inside(root, asset.path)
            with path.open("rb") as handle:
                raw = handle.read(asset.size + 1)
            if len(raw) != asset.size or hashlib.sha256(raw).hexdigest() != asset.sha256:
                errors.append("MEDIA_CHANGED:" + asset.id)
            if asset.id in used and asset.kind in {"image", "gif"} and not asset.decorative and not asset.alt.strip():
                errors.append("MEDIA_ALT_REQUIRED:" + asset.id)
            if public and asset.id in used and not asset.public_url:
                errors.append("MEDIA_UNRESOLVED:" + asset.id)
        except (RunError, OSError):
            errors.append("MEDIA_MISSING:" + asset.id)
    return errors
