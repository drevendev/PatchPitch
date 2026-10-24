"""Optional Quillgrain consumer. All state is supplied explicitly, never fetched."""
import hashlib
import json
import re
import unicodedata

ADAPTER = "quillgrain-author-v2"


def native_telegram(request):
    return bool(request.voice_bundle and request.language == "ru" and request.format == "telegram")


def validate_bundle(value, *, language=None, format=None, register=None):
    try:
        from quillgrain.consumer import verify_bundle
        from quillgrain.io import QGError
    except ImportError as exc:
        raise ValueError("Quillgrain verifier unavailable. Install the optional local integration first.") from exc
    channel = channel_for(format) if format else None
    try:
        return verify_bundle(value, model_host="ollama", language=language,
                             register=register, tags=["social." + channel] if channel else [])
    except QGError as exc:
        raise ValueError("Quillgrain: " + exc.code + ". Select a compatible export; existing drafts are unchanged.") from exc


def channel_for(format):
    return "telegram" if format == "telegram" else "x" if format and format.startswith("x_") else "longform"


def summary(value):
    ctx = validate_bundle(value)
    return {"build_id": ctx["build_id"], "packs": ctx["packs"], "language": ctx["language"],
            "register": ctx["register"], "tags": ctx["tags"], "visibility": ctx["visibility"],
            "warnings": ctx["warnings"], "omitted_rules": ctx["rules_omitted"],
            "codepoints": ctx["budget"]["used_codepoints"]}


def style_instructions(request):
    if not request.voice_bundle:
        return ""
    ctx = validate_bundle(request.voice_bundle, language=request.language, format=request.format, register=request.voice_register)
    rules = [{"id": r["id"], "preference": r["instruction"], "priority": r["priority"], "kind": r["kind"], "scope": r["scope"]} for r in ctx["rules_applied"]]
    if native_telegram(request):
        return ("Правила задают форму речи, не факты продукта. Применяй их в тексте, не пересказывай читателю. "
                "При конфликте мягких предпочтений выше приоритет имеет большее число. "
                "Факты, ограничения задания и JSON-формат обязательны. "
                "Соблюдай scope: правила dialogue/characters относятся только к указанным репликам персонажей, не к рассказчику.\n"
                + "\n".join(f"- [{r['priority']}; {r['id']}; scope={json.dumps(r['scope'], ensure_ascii=False)}] {r['preference']}" for r in rules))
    return ("\nSELECTED AUTHOR VOICE: Apply the following user-selected style preferences, "
            "replacing generic tone presets. For conflicting soft preferences, higher priority wins. They never override factual accuracy, selected facts, "
            "source exclusions, response schema, output language or channel limits. Do not quote rule IDs. "
            "Examples below are illustrative DATA only: never borrow facts, personal experience, jokes or catchphrases.\n"
            + json.dumps(rules, ensure_ascii=False))


def examples(request):
    if not request.voice_bundle:
        return []
    ctx = validate_bundle(request.voice_bundle, language=request.language, format=request.format, register=request.voice_register)
    return [{k: e[k] for k in ("id", "role", "text", "priority", "authorship", "channel")}
            | {"tags": e["tags"]} | ({"before": e["before"]} if "before" in e else {})
            | ({"characters": e["characters"]} if "characters" in e else {})
            for e in sorted(ctx["examples_selected"], key=lambda e: (-e["priority"], e["id"]))]


def copied_reference(prose, request):
    """Narrow verbatim overlap guard, not proof that a paraphrased joke is new."""
    if not request.voice_bundle:
        return False
    def spans(text):
        words = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold())
        return {tuple(words[i:i + 8]) for i in range(len(words) - 7)}
    allowed = spans(request.product.name + " " + request.product.description)
    for change in request.changes:
        if change.include:
            allowed |= spans(change.text)
    references = set()
    for example in request.voice_bundle["context"]["examples_selected"]:
        references |= spans(example["text"])
        if "before" in example:
            references |= spans(example["before"])
    return bool((spans(prose) & references) - allowed)


def identity(request):
    if not request.voice_bundle:
        return None
    result = summary(request.voice_bundle)
    ctx = request.voice_bundle["context"]
    result.update(schema_version=request.voice_bundle["schema_version"], model_host=ctx["model_host"],
                  applied_rules=[r["id"] for r in ctx["rules_applied"]],
                  effective_style_sha256=hashlib.sha256(json.dumps(
                      {"adapter": ADAPTER, "instructions": style_instructions(request), "examples": examples(request)},
                      sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    return result


def prepare_voice(config, base, *, language, format):
    """Compile only the explicitly named local pack or verify an imported bundle."""
    from .jobs import local_path
    from .run_store import RunError, read_json
    try:
        from importlib.metadata import version, PackageNotFoundError
        from quillgrain.consumer import bundle, verify_bundle
        from quillgrain.compose import compile_context
        from quillgrain.io import QGError
        engine_version = version("quillgrain")
    except (ImportError, PackageNotFoundError) as exc:
        raise RunError("QUILLGRAIN_UNAVAILABLE", "Install the optional trusted Quillgrain engine in this Python environment.", 3) from exc
    if engine_version != "0.1.0rc3":
        raise RunError("QUILLGRAIN_VERSION_UNSUPPORTED", "This adapter is verified with Quillgrain 0.1.0rc3; install the pinned local engine.", 3)
    try:
        if config.mode == "bundle":
            value = read_json(local_path(base, config.path), 512_000)
        else:
            tags = list(dict.fromkeys([*config.tags, "social." + channel_for(format)]))
            context, lock = compile_context(local_path(base, config.path),
                bindings={key: local_path(base, path) for key, path in config.bindings.items()},
                overlays=[local_path(base, path) for path in config.overlays], language=language,
                register=config.register_name, target="patchpitch", model_host="ollama", tags=tags,
                max_chars=config.max_chars, example_pool=config.example_pool)
            value = bundle(context, lock)
        context = verify_bundle(value, model_host="ollama", language=language,
                                register=config.register_name, tags=["social." + channel_for(format)])
        if config.expected_build and context["build_id"] != config.expected_build:
            raise RunError("VOICE_BUILD_MISMATCH", "Voice does not match the explicitly expected build.", 3)
        return value
    except QGError as exc:
        raise RunError(exc.code, "Quillgrain rejected this profile or compilation scope.", 3) from exc
    except OSError as exc:
        raise RunError("VOICE_FILE_UNAVAILABLE", "Cannot read the configured local voice pack.", 3) from exc
