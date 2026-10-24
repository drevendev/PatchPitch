import json
import hashlib
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import __version__
from . import generator
from . import telemetry
from .models import PitchInput, PrepareInput, SocialInput
from . import social, fact_packs, sessions, git_import, voice, hashtags, longform
from .run_store import RunError
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
# Provenance and current-thread context are outside the model's fact budget, but
# can exceed the original 32 KB transport cap within their existing field limits.
REQUEST_LIMITS = {"/api/voice/validate": 512_000,"/api/session/validate": sessions.SAVE_FILE_BYTES, "/api/pitch": 1_000_000, "/api/social": 1_000_000}
REQUEST_LIMITS.update({"/api/hashtags/validate": 1_000_000, "/api/hashtags/check": 1_000_000, "/api/longform": 1_000_000})
REQUEST_LIMITS["/api/editorial"] = 1_000_000


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
        limit = REQUEST_LIMITS.get(request.url.path, 32_000)
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > limit:
                return JSONResponse({"error": {"code": "input_too_large", "message": "Input is too large."}}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers.update({"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    # Never echo private voice bundles/input through FastAPI validation errors.
    return JSONResponse({"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]}, status_code=422)


@app.post("/api/voice/validate")
def validate_voice(request: dict):
    try:
        return {"summary": voice.summary(request)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


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


@app.post("/api/hashtags/validate")
def validate_catalog(request: hashtags.Catalog):
    return {"id": request.id, "version": request.version, "tags": len(request.tags)}


@app.post("/api/hashtags/check")
def check_social_export(request: dict):
    try:
        original = SocialInput.model_validate(request["input_snapshot"])
        if original.hashtag_policy != hashtags.POLICY:
            raise RunError("LEGACY_X", "This draft uses legacy X formatting; review it separately.", 4)
        plans = {p.id: p for p in original.hashtag_plan}
        posts = [sessions.SavedPost.model_validate(p) for p in request["posts"]]
        if len(posts) != len(plans) or {p.id for p in posts} != set(plans):
            raise RunError("X_POST_PLAN", "The current post list differs from the saved plan.", 4)
        for post in posts:
            hashtags.validate_export_post(original, post.model_dump())
        return {"status": "passed", "policy": hashtags.POLICY}
    except RunError as exc:
        return JSONResponse({"error": exc.as_dict()}, status_code=422)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, "Invalid current X export or input snapshot.")


@app.post("/api/longform")
async def longform_pitch(request: longform.LongformInput):
    return await run_generation(request, longform.generate)


@app.post("/api/prepare")
def prepare(request: PrepareInput):
    try:
        return {"changes": prepare_lines(request.text)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/pitch")
async def pitch(request: PitchInput):
    return await run_generation(request, generator.generate)


@app.post("/api/session/validate")
def validate_session(request: dict):
    try:
        return sessions.validate_file(request)
    except ValueError as exc:
        # Do not echo private saved input through Pydantic's input field.
        raise HTTPException(422, "Invalid save file: check version, structure and source references.") from exc


@app.post("/api/social")
async def social_pitch(request: SocialInput):
    return await run_generation(request, social.generate)


@app.post("/api/git/inspect")
def inspect_git(request: git_import.InspectInput):
    return git_read(git_import.inspect, request)


@app.post("/api/git/preview")
def preview_git(request: git_import.PreviewInput):
    return git_read(git_import.preview, request)


def git_read(function, request):
    try:
        return function(request)
    except generator.GenerationError as exc:
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)


@app.post("/api/git/facts")
async def extract_git_facts(request: git_import.ExtractInput):
    return await run_generation(request, git_import.extract)


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
    except RunError as exc:
        return JSONResponse({"error": exc.as_dict()}, status_code=422)
    finally:
        generation_lock.release()


from .editorial_api import register as register_editorial
register_editorial(app)
