"""Conservative estimate, NOT an implementation of X/twitter-text validation.

Uses v3 weight ranges, NFC and 23 characters per recognized URL. Extraction is
bounded to ASCII DNS hosts (including punycode), optional ports and HTTP(S) or
bare domains. This is not the complete twitter-text TLD/IDN/emoji algorithm;
unsupported or malformed candidates retain their raw weight. Mirrored in JS.
"""
import re
import unicodedata

POLICY = "x-estimate-v2"
_CANDIDATE = re.compile(
    r"(?<![\w@/#$.-])(?:https?://|www\.|[A-Za-z0-9_-]+\.)[^\s<>\x00-\x1f\x7f\"'`\u2018\u2019\u201c\u201d]+", re.I)
_AUTHORITY = re.compile(r"([A-Za-z0-9.-]+)(?::([0-9]{1,5}))?", re.ASCII)
_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", re.ASCII)
_TLD = re.compile(r"(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9-]{1,59})", re.ASCII | re.I)
_TRAILING = ".,!?;:\u2026"
_PAIRS = {")": "(", "]": "[", "}": "{"}


def url_spans(text):
    """Yield supported URL spans, excluding surrounding sentence punctuation."""
    for match in _CANDIDATE.finditer(text):
        token = match[0]
        stack = []
        for index, char in enumerate(token):
            if char in "([{":
                stack.append((char, index))
            elif char in ")]}":
                if not stack or stack[-1][0] != _PAIRS[char]:
                    token = token[:index]
                    break
                stack.pop()
        if stack:
            token = token[:stack[0][1]]
        token = token.rstrip(_TRAILING)
        authority = re.split(r"[/?#]", re.sub(r"^https?://", "", token, flags=re.I), 1)[0]
        host_port = _AUTHORITY.fullmatch(authority)
        if not host_port:
            continue
        host, port = host_port.groups()
        labels = host.split(".")
        if (len(host) > 253 or len(labels) < 2 or not all(_LABEL.fullmatch(label) for label in labels)
                or not _TLD.fullmatch(labels[-1]) or (port and not 1 <= int(port) <= 65535)):
            continue
        yield match.start(), match.start() + len(token)


def strip_urls(text):
    """Mask only recognized URLs, leaving outside hashtags/punctuation intact."""
    parts, previous = [], 0
    for start, end in url_spans(text):
        parts.extend((text[previous:start], " "))
        previous = end
    return "".join(parts) + text[previous:]


def weight(char):
    n = ord(char)
    return 1 if n <= 4351 or 8192 <= n <= 8205 or 8208 <= n <= 8223 or 8242 <= n <= 8247 else 2


def estimate(text):
    text = unicodedata.normalize("NFC", text)
    count = sum(map(weight, text))
    for start, end in url_spans(text):
        count += 23 - sum(map(weight, text[start:end]))
    return {"characters": count, "limit": 280, "policy": POLICY,
            "estimated": True, "over_limit": count > 280, "requires_x_preview": True}
