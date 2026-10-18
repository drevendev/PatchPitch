import hashlib
import copy
import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .models import Draft, PITCH_SCHEMA, PitchInput
from .validation import DraftError, blocks, markdown, validate_draft

OLLAMA = "http://127.0.0.1:11434"
MODEL = os.getenv("PATCHPITCH_MODEL", "gemma3:4b")
TIMEOUT = min(max(float(os.getenv("PATCHPITCH_TIMEOUT", "180")), 1), 600)
OPTIONS = {"temperature": 0.2, "seed": 42, "num_predict": 1000, "num_ctx": 4096}
PROMPT = (Path(__file__).parent / "prompts" / "release.txt").read_text(encoding="utf-8")
# Never inherit a system HTTP proxy for unpublished local notes.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class GenerationError(Exception):
    code: str
    message: str
    status: int = 502


def ollama_json(path: str, payload=None, timeout=5):
    request = urllib.request.Request(OLLAMA + path, data=None if payload is None else json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(request, timeout=timeout) as response:
            data = response.read(128_001)
        if len(data) > 128_000:
            raise GenerationError("invalid_response", "Ollama returned an oversized response. Try again manually.")
        return json.loads(data)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise GenerationError("model_missing", f"Model {MODEL} is unavailable. Run ollama pull {MODEL}.", 503) from exc
        raise GenerationError("ollama_error", "Ollama could not complete this request. Check its local log.") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise GenerationError("timeout", "The local model timed out. Your input is still here; try again manually.", 504) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise GenerationError("timeout", "The local model timed out. Your input is still here.", 504) from exc
        raise GenerationError("ollama_unavailable", "Ollama is not reachable at 127.0.0.1:11434. Start Ollama and try again.", 503) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GenerationError("invalid_json", "Ollama returned invalid JSON. Try again manually.") from exc


def model_input(request: PitchInput):
    return {"product": request.product.model_dump(), "audience": request.audience, "release_label": request.release_label,
            "selected_changes": [{"id": c.id, "text": c.text} for c in request.changes if c.include]}


def build_payload(request: PitchInput):
    schema=copy.deepcopy(PITCH_SCHEMA)
    allowed=[change.id for change in request.changes if change.include]
    for definition in schema["$defs"].values():
        ids=definition.get("properties",{}).get("source_ids")
        if ids:
            ids["items"]={"type":"string","enum":allowed}
            ids["maxItems"]=len(allowed)
            ids["uniqueItems"]=True
    return {"model": MODEL, "stream": False, "format": schema,
            "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": json.dumps(model_input(request), ensure_ascii=False)}],
            "options": OPTIONS, "keep_alive": "10m"}


def generate(request: PitchInput):
    start = time.perf_counter()
    raw = ollama_json("/api/chat", build_payload(request), timeout=TIMEOUT)
    elapsed = round(time.perf_counter() - start, 3)
    try:
        if not raw.get("done") or raw.get("done_reason") == "length":
            raise GenerationError("incomplete_response", "The model did not finish its draft. Try again manually.")
        draft = Draft.model_validate_json(raw["message"]["content"])
        warnings = validate_draft(draft, request)
    except GenerationError:
        raise
    except (ValidationError, KeyError, TypeError, AttributeError, DraftError) as exc:
        message = str(exc) if isinstance(exc, DraftError) else "The model returned invalid JSON or an invalid draft structure. Try again manually."
        raise GenerationError("invalid_draft", message) from exc
    sources = {c.id: c.text for c in request.changes if c.include}
    return {"draft": draft.model_dump(), "markdown": markdown(draft, request.cta_text), "warnings": warnings,
            "sources": sources, "source_map": [{"block": label, "source_ids": block.source_ids} for label, block in blocks(draft)],
            "meta": {"mode": "LIVE_MODEL", "model": raw.get("model", MODEL), "elapsed_seconds": elapsed, "options": OPTIONS, "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
                     "prompt_eval_count": raw.get("prompt_eval_count"), "eval_count": raw.get("eval_count"), "total_duration_ns": raw.get("total_duration")}}
