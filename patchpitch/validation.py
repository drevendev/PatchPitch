import re

from .models import Draft, PitchInput, PostDraft


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
    lowered = text.lower()
    lowered = re.sub(r"\b(?:higher|lower|previous|next|other|which) one\b", " ", lowered)
    tens = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90}
    units = "one|two|three|four|five|six|seven|eight|nine"
    compounds = set()
    def read_compound(match):
        compounds.add(str(tens[match[1]] + int(NUMBER_WORDS.get(match[2], "0"))))
        return " "
    lowered = re.sub(r"\b(" + "|".join(tens) + r")(?:[- ](" + units + r"))?\b",read_compound,lowered)
    words = re.findall(r"\b(?:" + "|".join(NUMBER_WORDS) + r")\b", lowered)
    return digits | compounds | {NUMBER_WORDS[word] for word in words}


def covered_list_counts(source, prose):
    """A fully named list need not repeat its count; an inspection aid only."""
    counts = set()
    number = r"\d{1,2}|" + "|".join(NUMBER_WORDS)
    pattern = r"\b(" + number + r")\s+(?:[\w-]+\s+){0,3}(?:goods|items|products|materials)\s*:\s*([^.!?]+)"
    for match in re.finditer(pattern, source, re.I):
        raw_count = match[1].lower()
        count = int(NUMBER_WORDS.get(raw_count, raw_count))
        names = [re.sub(r"^and\s+", "", name.strip(), flags=re.I) for name in match[2].split(",")]
        if len(names) == count and all(re.search(r"\b" + re.escape(name) + r"s?\b", prose, re.I) for name in names):
            counts.add(str(count))
    return counts


def required_note_ids(request: PitchInput) -> list[str]:
    # Narrow, explicit owner instructions; this does not infer release safety.
    pattern=r"\b(?:export|make|keep|create|take)\b[^.]{0,60}\bbackup\b|\b(?:keep|save|download)\s+(?:(?:an?|the|your)\s+)?export\b|\bnot backward compatible\b|\bbreaking change\b"
    return [c.id for c in request.changes if c.include and re.search(pattern,c.text,re.I)]


def guidance_requirements(request):
    """Narrow lexical checks for explicit backup guidance, not semantic proof."""
    ids=set(required_note_ids(request))
    source=" ".join(c.text for c in request.changes if c.id in ids)
    if not re.search(r"\bbackup\b|\bexport\b",source,re.I):
        return []
    checks=[("backup or export",r"\bbackup\b|\bexport\b")]
    for label, pattern in [
        ("Settings",r"\bsettings\b"),
        ("changing or moving devices",r"\b(?:chang\w*|mov\w*|switch\w*|transfer\w*)\b[^.!?]{0,35}\bdevices?\b"),
        ("clearing browser data",r"\b(?:clear\w*|delet\w*|wip\w*|eras\w*)\b[^.!?]{0,35}\b(?:browser\s+)?data\b"),
    ]:
        if re.search(pattern,source,re.I):checks.append((label,pattern))
    return checks


def prepare_lines(text: str) -> list[dict]:
    lines = [re.sub(r"^\s*[-*+]\s+", "", line).strip() for line in text.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 15 or sum(map(len, lines)) > 6000:
        raise ValueError("Use 1–15 lines and at most 6,000 characters of change notes.")
    unreleased_level = None
    result = []
    for i, line in enumerate(lines, 1):
        heading = re.match(r"^(#{1,6})\s", line)
        if heading:
            level = len(heading[1])
            if unreleased_level is not None and level <= unreleased_level:
                unreleased_level = None
            if re.search(r"\bunreleased\b", line, re.I):
                unreleased_level = level if unreleased_level is None else min(level, unreleased_level)
        marker = re.search(r"\[(planned|internal|blocked|unknown)\]", line, re.I)
        reason = f"Marked {marker.group(1).lower()}" if marker else ("Unreleased section — review availability" if unreleased_level is not None or re.search(r"\bunreleased\b", line, re.I) else "")
        result.append({"id": f"C{i:02}", "text": line, "include": not bool(reason), "reason": reason})
    return result


def blocks(draft: Draft):
    if isinstance(draft, PostDraft):
        yield "Post", draft
        return
    yield "Title", draft.title
    yield "Introduction", draft.intro
    for i, block in enumerate(draft.highlights, 1):
        yield f"Highlight {i}", block
    for i, block in enumerate(draft.details, 1):
        yield f"Detail {i}", block
    if draft.note:
        yield "Note", draft.note


def block_text(block):
    return " ".join(part for part in [block.text, *getattr(block, "retained_facts", [])] if part)


def validate_draft(draft: Draft, request: PitchInput) -> list[str]:
    post = isinstance(draft, PostDraft)
    if not post and re.search(r"[-–—,:;]$",draft.title.text):
        raise DraftError("The headline appears cut off. Please generate again.")
    required_notes=required_note_ids(request)
    note_ids = draft.source_ids if post else (draft.note.source_ids if draft.note else [])
    if not set(required_notes) <= set(note_ids):
        raise DraftError("The draft omitted an explicit backup or compatibility note. Please generate again.")
    if post:
        missing=[label for label,pattern in guidance_requirements(request) if not re.search(pattern,draft.text,re.I)]
        if missing:
            raise DraftError("The post left out backup guidance: " + ", ".join(missing) + ". Choose a longer format or generate again manually.")
    allowed = {c.id for c in request.changes if c.include}
    sources = {c.id: c.text for c in request.changes if c.include}
    context = " ".join([request.product.name, request.product.description, request.release_label])
    warnings = []
    used={source for _,block in blocks(draft) for source in block.source_ids}
    unused=allowed-used
    if unused:
        warnings.append("Selected facts not referenced in this draft: " + ", ".join(sorted(unused)) + ". Check whether an important change was omitted.")
    for label, block in blocks(draft):
        prose = block_text(block)
        if re.search(r"\bC\d{2}\b|(?<!\w)#[A-Za-z]",prose):
            raise DraftError("The model put source IDs or hashtags inside its prose. Please generate again.")
        if label != "Title" and not re.search(r"[.!?…][\"'’”)]?$", prose):
            raise DraftError(f"{label} appears cut off or unfinished. Please generate again.")
        if len(set(block.source_ids)) != len(block.source_ids):
            raise DraftError(f"{label} contains duplicate source IDs. Please generate again.")
        if not set(block.source_ids) <= allowed:
            raise DraftError(f"{label} cites an unknown or excluded source ID. Please generate again.")
        source_text = context + " " + " ".join(sources[source] for source in block.source_ids)
        if (re.search(r"\bordered\b|\bqueue\b",source_text,re.I)
                and re.search(r"\bat once\b|\bparallel\b|\bsimultaneous\w*\b",prose,re.I)
                and not re.search(r"\bat once\b|\bparallel\b|\bsimultaneous\w*\b",source_text,re.I)):
            raise DraftError(f"{label} describes an ordered plan as simultaneous work. Please generate again.")
        if re.search(r"\b(TODO|TBD|FIXME|lorem ipsum|placeholder)\b|\[\[", prose, re.I):
            raise DraftError("The model left a placeholder. Please generate again.")
        for url in re.findall(r"https?://[^\s<>]+", prose):
            if url not in source_text:
                warnings.append(f"{label}: check a link that was not present in the selected input.")
        for number in sorted(numeric_claims(prose)):
            if number not in numeric_claims(source_text):
                warnings.append(f"{label}: check the number “{number}”; it was not in this block's cited facts.")
        if label.startswith("Highlight") or label == "Post":
            source_numbers = numeric_claims(" ".join(sources[source] for source in block.source_ids))
            omitted = source_numbers - numeric_claims(prose) - covered_list_counts(source_text, prose)
            if len(source_numbers) >= 2 and omitted:
                warnings.append(f"{label}: source numbers not mentioned: {', '.join(sorted(omitted))}. Check whether a limit or prerequisite was lost.")
        for claim in re.findall(r"\b(?:unaffected|guarantee[sd]?|always|never)\b", prose, re.I):
            if not re.search(r"\b" + re.escape(claim) + r"\b", source_text, re.I):
                warnings.append(f"{label}: check the scope of “{claim}”; that absolute wording was not in its cited facts.")
    return list(dict.fromkeys(warnings))


def markdown(draft: Draft | PostDraft, cta: str = "", *, include_tags: bool = True) -> str:
    def safe(text):
        return text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")
    post = isinstance(draft, PostDraft)
    parts = [draft.text.replace("<", "&lt;").replace(">", "&gt;")] if post else ["# " + safe(block_text(draft.title)), safe(block_text(draft.intro)), "\n".join("- " + safe(block_text(b)) for b in draft.highlights)]
    if not post and draft.details:
        parts.extend(["## Also in this update", "\n".join("- " + safe(block_text(b)) for b in draft.details)])
    if not post and draft.note:
        parts.append("**Note:** " + safe(block_text(draft.note)))
    if cta:
        parts.append(safe(cta))
    if include_tags and draft.hashtags:
        parts.append(" ".join(draft.hashtags))
    return "\n\n".join(parts) + "\n"
