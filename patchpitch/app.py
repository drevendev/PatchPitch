import json
import hashlib
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import __version__
from . import generator
from . import telemetry
from .models import PitchInput, PrepareInput, SocialInput
from . import social, fact_packs
from .validation import prepare_lines
from .build import source_hash

STATIC = Path(__file__).parent / "static"
RUNTIME_SOURCE_SHA256 = source_hash()


@asynccontextmanager
async def lifespan(app):
    telemetry.configure()
    try:
        yield
    finally:
        await run_in_threadpool(telemetry.shutdown)


app = FastAPI(title="PatchPitch", version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
generation_lock = threading.Lock()


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.headers.get("host", "")
    try:
        parsed = urlsplit("http://" + host)
        valid_host = parsed.hostname in {"127.0.0.1", "localhost"} and not parsed.username and not parsed.password and parsed.path == ""
        origin = request.headers.get("origin")
        if not valid_host or (origin and origin != "http://" + host):
            return JSONResponse({"error": {"code": "local_only", "message": "Use the local PatchPitch address."}}, status_code=403)
    except ValueError:
        return JSONResponse({"error": {"code": "local_only", "message": "Invalid local address."}}, status_code=403)
    if request.method == "POST":
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"error": {"code": "json_required", "message": "Send JSON input."}}, status_code=415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 32_000:
                return JSONResponse({"error": {"code": "input_too_large", "message": "Input is too large."}}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers.update({"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    return response


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    try:
        version = generator.ollama_json("/api/version")
        tags = generator.ollama_json("/api/tags")
        model = next((m for m in tags.get("models", []) if m.get("name") == generator.MODEL), None)
        return {"app": __version__, "runtime_source_sha256": RUNTIME_SOURCE_SHA256, "mode": "LOCAL", "sentry_enabled": telemetry.enabled(), "ollama": "ready" if model else "model_missing", "ollama_version": version.get("version"), "model": generator.MODEL, "digest": model.get("digest") if model else None,
                "options": generator.OPTIONS, "prompt_sha256": hashlib.sha256(generator.read_prompt().encode()).hexdigest(),
                "prompt_hashes": {fmt:hashlib.sha256(generator.read_prompt(fmt).encode()).hexdigest() for fmt in ("devlog","community","short")}}
    except generator.GenerationError as exc:
        return {"app": __version__, "runtime_source_sha256": RUNTIME_SOURCE_SHA256, "mode": "LOCAL", "sentry_enabled": telemetry.enabled(), "ollama": exc.code, "model": generator.MODEL, "options": generator.OPTIONS, "message": exc.message}


@app.post("/api/prepare")
def prepare(request: PrepareInput):
    try:
        return {"changes": prepare_lines(request.text)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/pitch")
async def pitch(request: PitchInput):
    return await run_generation(request, generator.generate)


@app.post("/api/social")
async def social_pitch(request: SocialInput):
    return await run_generation(request, social.generate)


@app.get("/api/fact-packs/{pack_id}")
def builtin_pack(pack_id: str):
    try:
        return fact_packs.prepare_pack(fact_packs.load_pack(pack_id))
    except KeyError:
        raise HTTPException(404, "Unknown built-in fact pack.")


@app.post("/api/fact-packs/prepare")
def import_pack(request: fact_packs.FactPack):
    return fact_packs.prepare_pack(request)


async def run_generation(request, generate):
    if not generation_lock.acquire(blocking=False):
        return JSONResponse({"error": {"code": "busy", "message": "A draft is already being generated. Please wait."}}, status_code=409)
    try:
        return await run_in_threadpool(generate, request)
    except generator.GenerationError as exc:
        body = {"error": {"code": exc.code, "message": exc.message}}
        if exc.evidence is not None:
            body["evidence"] = exc.evidence
        return JSONResponse(body, status_code=exc.status)
    finally:
        generation_lock.release()
