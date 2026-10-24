"""Small, trusted writing presets; source text never defines the instructions."""
import re
from .validation import guidance_requirements

FORMATS = {
    "telegram": {"label": "Telegram post", "limit": 4096,
                 "instruction": "Write one Telegram post in connected paragraphs, normally 150–250 words. Speak directly to the author's own channel readers, in the first person when supplied facts authorize it. Start with the actual thing the author did, rather than an abstract project progress report. Keep the supplied voice's colloquial register; do not turn it into a third-person feature overview. A short personal opening is allowed only when supported by supplied facts. Explain how the thing works and why the author uses it. Preserve line breaks. Optional **emphasis** and ~~strikethrough~~ are allowed, not required. No headings or checklist unless specifically useful. Source IDs and hashtags belong only in their arrays, never prose. Do not invent jokes or copy catchphrases from samples. Preserve historical vs new status explicitly when supplied; do not call an old patch new. Finish with ordinary prose, never leftover JSON syntax or escaped schema fragments."},
    "devlog": {"label": "Devlog", "limit": None,
               "instruction": "Write the full release announcement using the supplied outline. Cover every selected topic and its meaningful limits."},
    "community": {"label": "Community post", "limit": 1600,
                  "instruction": "Write an inviting community post in 80–140 words. Name the product and its character, then explain two or three useful changes in connected prose. No title, list, greeting, Markdown or invented invitation. Omit secondary topics instead of squeezing in a changelog. Preserve prerequisites and exceptions for any feature you mention."},
    "short": {"label": "Short post", "limit": 280,
              "instruction": "Write a short social post in roughly 25–35 words. Start with the product name and ONE simple useful change; place any required guidance after that benefit. Choose a change that fits with its necessary qualifications. If a complex feature cannot fit accurately, choose a simpler one. No title, list, Markdown, source-ID annotations, links or hashtags in the text field. Do not repeat the version label unless essential. Do not try to summarize every source. Prefer one complete, specific thought over a vague list."},
}
STYLES = {
    "voice": {"label": "Quillgrain voice", "instruction": "Use the selected Quillgrain author voice. No generic tone preset."},
    "warm": {"label": "Warm", "instruction": "Use a warm, thoughtful maker voice. A little character, concrete details, no hype or invented lore. Respect the supplied voice sample for rhythm only."},
    "clear": {"label": "Clear", "instruction": "Use calm, direct, factual language. Lead with what the reader can now do. Avoid metaphors, sales adjectives and exclamation marks; keep the product's own terminology."},
    "lively": {"label": "Lively", "instruction": "Use brisk, upbeat, specific language with varied sentence rhythm. Keep enthusiasm restrained: no superlatives, urgency, exaggerated benefits or invented claims. At most one exclamation mark."},
}


def tag_limit(request):
    return 5 if request.format == "telegram" else 1 if request.format == "short" else 3


def tag_candidates(request):
    """Conservative candidates from product context and included facts, never plans.

    Gemma chooses up to three. Restricting the vocabulary prevents unsupported
    platform/trend tags from becoming factual claims in the exported post.
    """
    if not request.auto_tags:
        return []
    if request.tag_allowlist:
        return list(dict.fromkeys(request.tag_allowlist))
    words = re.findall(r"[A-Za-z0-9]+", request.product.name)
    name = "".join(w[:1].upper() + w[1:] for w in words)
    candidates = ["#" + name] if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,39}", name) else []
    context = " ".join([request.product.name, request.product.description,
                        *(c.text for c in request.changes if c.include)]).lower()
    for pattern, tag in [(r"\bidle\s+game\b", "#IdleGame"), (r"\bcraft(?:ing)?\b", "#Crafting"),
                         (r"\bnotes?\b", "#Notes"), (r"\bmarkdown\b", "#Markdown"),
                         (r"\baccessibility\b", "#Accessibility"), (r"\bdeveloper\s+tool\b", "#DevTools")]:
        if re.search(pattern, context):
            candidates.append(tag)
    return list(dict.fromkeys(candidates))[:6]


def writing_instructions(request):
    preset = FORMATS[request.format]
    instructions = preset["instruction"] + "\nSTYLE: " + STYLES[request.style]["instruction"]
    if request.format != "devlog":
        # Reserve the exact owner CTA, separators and longest possible tag line.
        candidates = tag_candidates(request)
        maximum_tags = min(tag_limit(request), len(candidates))
        tag_budget = sum(sorted((len(t) for t in candidates), reverse=True)[:maximum_tags])
        if candidates:
            tag_budget += maximum_tags - 1 + 2
        cta_budget = len(request.cta_text) + 2 if request.cta_text else 0
        budget = preset["limit"] - cta_budget - tag_budget
        if request.format == "short":
            budget -= 30  # Writing headroom; the real exported limit remains 280.
        instructions += (f"\nYour text field has at most {budget} Unicode characters, including spaces. "
                         "Leave enough space for a complete final sentence. Required backup/breaking guidance must be stated with its precise circumstances; it may not be silently omitted. "
                         "Cite only source IDs actually used in your post. Unmentioned sources will be shown as left out. Do not invent new facts from the voice sample. Return only text, source_ids and hashtags.")
    instructions += (f"\nHASHTAGS: Choose zero to {tag_limit(request)} useful tags ONLY from tag_candidates. Put them in hashtags, never prose. "
                     "Tags are suggestions, not evidence of reach or trends." if request.auto_tags else
                     "\nHASHTAGS: Disabled. Return hashtags as an empty array; no hashtags in prose.")
    if request.format != "devlog" and guidance_requirements(request):
        instructions += "\nREQUIRED GUIDANCE: Explicitly include " + ", ".join(label for label,_ in guidance_requirements(request)) + ". Budget room for this while planning, but put it after the useful change in your final prose. Keep all listed circumstances; do not collapse them to generic advice."
    return instructions
