import re

from .models import Draft, PitchInput


class DraftError(ValueError):
    pass


NUMBER_WORDS = {word: str(i) for i, word in enumerate([
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
])}


def numeric_claims(text):
    """Inspection aid for digits and common spelled-out counts, not semantic proof."""
    digits = set(re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?:%)?", text))
    words = re.findall(r"\b(?:" + "|".join(NUMBER_WORDS) + r")\b", text.lower())
    return digits | {NUMBER_WORDS[word] for word in words}


def prepare_lines(text: str) -> list[dict]:
    lines = [re.sub(r"^\s*[-*+]\s+", "", line).strip() for line in text.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 15 or sum(map(len, lines)) > 6000:
        raise ValueError("Use 1–15 lines and at most 6,000 characters of change notes.")
    unreleased = False
    result = []
    for i, line in enumerate(lines, 1):
        if re.match(r"^#{1,6}\s", line):
            unreleased = bool(re.search(r"\bunreleased\b", line, re.I))
        marker = re.search(r"\[(planned|internal|blocked|unknown)\]", line, re.I)
        reason = f"Marked {marker.group(1).lower()}" if marker else ("Unreleased section — review availability" if unreleased or re.search(r"\bunreleased\b", line, re.I) else "")
        result.append({"id": f"C{i:02}", "text": line, "include": not bool(reason), "reason": reason})
    return result


def blocks(draft: Draft):
    yield "Title", draft.title
    yield "Introduction", draft.intro
    for i, block in enumerate(draft.highlights, 1):
        yield f"Highlight {i}", block
    if draft.note:
        yield "Note", draft.note


def validate_draft(draft: Draft, request: PitchInput) -> list[str]:
    allowed = {c.id for c in request.changes if c.include}
    source_text = " ".join([request.product.name, request.product.description, request.audience, request.release_label] + [c.text for c in request.changes if c.include])
    warnings = []
    for label, block in blocks(draft):
        if len(set(block.source_ids)) != len(block.source_ids):
            raise DraftError(f"{label} contains duplicate source IDs. Please generate again.")
        if not set(block.source_ids) <= allowed:
            raise DraftError(f"{label} cites an unknown or excluded source ID. Please generate again.")
        if re.search(r"\b(TODO|TBD|FIXME|lorem ipsum|placeholder)\b|\[\[", block.text, re.I):
            raise DraftError("The model left a placeholder. Please generate again.")
        for url in re.findall(r"https?://[^\s<>]+", block.text):
            if url not in source_text:
                warnings.append(f"{label}: check a link that was not present in the selected input.")
        for number in sorted(numeric_claims(block.text)):
            if number not in numeric_claims(source_text):
                warnings.append(f"{label}: check the number “{number}”; it was not in the selected input.")
    return list(dict.fromkeys(warnings))


def markdown(draft: Draft, cta: str = "") -> str:
    def safe(text):
        return text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")
    parts = ["# " + safe(draft.title.text), safe(draft.intro.text), "\n".join("- " + safe(b.text) for b in draft.highlights)]
    if draft.note:
        parts.append("**Note:** " + safe(draft.note.text))
    if cta:
        parts.append(safe(cta))
    return "\n\n".join(parts) + "\n"
