"""Conservative estimate, NOT an implementation of X/twitter-text validation.

Uses twitter-text v3 weight ranges, NFC and a URL reserve. Emoji sequences are
deliberately counted by code point. Long URLs keep their raw weight. Ambiguous
URLs and platform changes still require the real X composer. Mirrored in JS.
"""
import re
import unicodedata

POLICY = "x-estimate-v1"
URL = re.compile(r"(?:https?://|www\.)[^\s<>]+|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}(?:/[^\s<>]*)?", re.I)


def weight(char):
    n = ord(char)
    return 1 if n <= 4351 or 8192 <= n <= 8205 or 8208 <= n <= 8223 or 8242 <= n <= 8247 else 2


def estimate(text):
    text = unicodedata.normalize("NFC", text)
    count = sum(map(weight, text))
    for match in URL.finditer(text):
        token = match[0]
        # Reserve punctuation too: it may be outside X's recognized URL.
        trailing = len(token) - len(token.rstrip(".,!?;:)'\"…"))
        count += max(0, 23 + 2 * trailing - sum(map(weight, token)))
    return {"characters": count, "limit": 280, "policy": POLICY,
            "estimated": True, "over_limit": count > 280, "requires_x_preview": True}
