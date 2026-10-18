"""Opt-in, metadata-only Sentry tracing. No automatic framework/AI capture."""
import math
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime

import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import HttpTransport, Transport

from . import __version__

ERROR_CODES = frozenset({"invalid_draft", "incomplete_response", "format_overflow",
    "ollama_unavailable", "timeout", "ollama_error", "model_missing", "invalid_json",
    "invalid_response", "unexpected_error"})
FORMATS = frozenset({"devlog", "community", "short"})
SCENARIOS = frozenset({"LIVE_MODEL", "CONTROLLED_FAILURE"})
_client = None


def _attempt(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception:
        # Diagnostics must never replace the application's result or error.
        return None


def _model(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:@+\-]{0,199}", value) else None


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _timestamp(value):
    if _number(value):
        return value
    if isinstance(value, str):
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value
        except ValueError:
            pass
    return None


def _technical_data(data):
    result = {}
    if not isinstance(data, dict): return result
    for key, value in (data or {}).items():
        if key == "gen_ai.operation.name" and value == "chat": result[key] = value
        elif key == "gen_ai.provider.name" and value == "ollama": result[key] = value
        elif key in {"gen_ai.request.model", "gen_ai.response.model"} and _model(value): result[key] = value
        elif key in {"gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"} and type(value) is int and value >= 0: result[key] = value
        elif key == "patchpitch.duration_ms" and _number(value): result[key] = value
        elif key == "patchpitch.format" and isinstance(value, str) and value in FORMATS: result[key] = value
        elif key == "patchpitch.scenario" and isinstance(value, str) and value in SCENARIOS: result[key] = value
        elif key == "error.type" and isinstance(value, str) and value in ERROR_CODES: result[key] = value
    return result


def _trace(trace):
    result = {}
    for key, length in [("trace_id", 32), ("span_id", 16), ("parent_span_id", 16)]:
        value = trace.get(key)
        if isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value): result[key] = value
    if trace.get("op") in {"function", "gen_ai.chat", "validation"}: result["op"] = trace["op"]
    if trace.get("status") in {"ok", "internal_error", "invalid_argument", "deadline_exceeded", "unavailable"}: result["status"] = trace["status"]
    if trace.get("data"): result["data"] = _technical_data(trace["data"])
    return result


def metadata_event(event, hint=None):
    """Rebuild from a small allowlist; never sanitize by removing known secrets."""
    tags = event.get("tags", {})
    code = tags.get("error.code")
    transaction = event.get("type") == "transaction"
    if not transaction and code not in ERROR_CODES:
        return None
    result = {"platform": "python", "environment": "local"}
    event_id = event.get("event_id", "")
    if re.fullmatch(r"[0-9a-f]{32}", event_id): result["event_id"] = event_id
    for key in ("timestamp", "start_timestamp"):
        stamp = _timestamp(event.get(key))
        if stamp is not None: result[key] = stamp
    release = event.get("release", "")
    if release in {f"patchpitch@{__version__}"} or re.fullmatch(r"patchpitch@[0-9a-f]{40}", release): result["release"] = release
    result["tags"] = {k: v for k, v in tags.items() if
        (k == "patchpitch.format" and v in FORMATS) or
        (k == "patchpitch.scenario" and v in SCENARIOS) or
        (k == "error.code" and v in ERROR_CODES)}
    result["contexts"] = {"trace": _trace(event.get("contexts", {}).get("trace", {}))}
    if transaction:
        result.update(type="transaction", transaction="patchpitch.generate" if tags.get("patchpitch.scenario") != "CONTROLLED_FAILURE" else "patchpitch.controlled_failure",
                      transaction_info={"source": "custom"}, spans=[])
        for span in event.get("spans", []):
            if span.get("op") not in {"gen_ai.chat", "validation"}: continue
            safe = _trace(span)
            for key in ("start_timestamp", "timestamp"):
                stamp = _timestamp(span.get(key))
                if stamp is not None: safe[key] = stamp
            model = _model(span.get("data", {}).get("gen_ai.request.model"))
            safe["description"] = f"chat {model}" if span["op"] == "gen_ai.chat" and model else "validate draft"
            result["spans"].append(safe)
    else:
        result.update(level="error", message=f"PatchPitch generation failed: {code}",
                      fingerprint=["patchpitch", code, result["tags"].get("patchpitch.scenario", "LIVE_MODEL")])
    return result


def metadata_envelope(envelope):
    # Dynamic-sampling baggage, SDK additions and attachments are not forwarded.
    headers = {}
    event_id = envelope.headers.get("event_id", "")
    if re.fullmatch(r"[0-9a-f]{32}", event_id): headers["event_id"] = event_id
    stamp = _timestamp(envelope.headers.get("sent_at"))
    if stamp is not None: headers["sent_at"] = stamp
    safe = Envelope(headers=headers)
    for item in envelope.items:
        if item.type not in {"event", "transaction"}: continue
        event = metadata_event(item.payload.json or {})
        if event:
            if item.type == "transaction": safe.add_transaction(event)
            else: safe.add_event(event)
    return safe


class MetadataTransport(Transport):
    def __init__(self, options, delegate_type=HttpTransport):
        super().__init__(options)
        self.delegate = delegate_type(options)

    def capture_envelope(self, envelope):
        def deliver():
            safe = metadata_envelope(envelope)
            if safe.items: self.delegate.capture_envelope(safe)
        _attempt(deliver)

    def flush(self, timeout, callback=None):
        _attempt(self.delegate.flush, timeout, callback)

    def kill(self):
        _attempt(self.delegate.kill)


def configure(*, dsn=None, transport_type=HttpTransport):
    """Only PATCHPITCH_SENTRY_DSN opts in; generic SENTRY_DSN is ignored."""
    global _client
    shutdown()
    value = os.getenv("PATCHPITCH_SENTRY_DSN", "") if dsn is None else dsn
    if not value: return False
    class BoundTransport(MetadataTransport):
        def __init__(self, options): super().__init__(options, transport_type)
    sha = os.getenv("PATCHPITCH_SENTRY_RELEASE", "")
    release = sha if re.fullmatch(r"[0-9a-f]{40}", sha) else __version__
    try:
        _client = sentry_sdk.Client(dsn=value, transport=BoundTransport,
            release=f"patchpitch@{release}", environment="local", server_name="patchpitch-local",
            default_integrations=False, auto_enabling_integrations=False,
            send_default_pii=False, include_local_variables=False, include_source_context=False,
            max_request_body_size="never", enable_logs=False, enable_metrics=False,
            auto_session_tracking=False, send_client_reports=False, enable_backpressure_handling=False,
            traces_sample_rate=1.0, profiles_sample_rate=0.0, trace_propagation_targets=[],
            trace_lifecycle="static", stream_gen_ai_spans=False,
            before_send=metadata_event, before_send_transaction=metadata_event,
            before_breadcrumb=lambda *args: None, transport_queue_size=20, shutdown_timeout=2)
        return True
    except Exception:
        _client = None
        return False


def enabled():
    return _client is not None


def flush(timeout=2):
    if _client: _attempt(_client.flush, timeout=timeout)


def shutdown():
    global _client
    if _client: _attempt(_client.close, timeout=2)
    _client = None


class ObservedSpan:
    def __init__(self, span): self.span = span

    def data(self, key, value):
        if self.span and _technical_data({key: value}): _attempt(self.span.set_data, key, value)

    def response(self, raw):
        if not isinstance(raw, dict): return
        # Observed identity only. Never substitute the configured request model.
        self.data("gen_ai.response.model", raw.get("model"))
        self.data("gen_ai.usage.input_tokens", raw.get("prompt_eval_count"))
        self.data("gen_ai.usage.output_tokens", raw.get("eval_count"))


class Generation:
    def __init__(self, format, scenario):
        self.format = format if format in FORMATS else "devlog"
        self.scenario = scenario if scenario in SCENARIOS else "LIVE_MODEL"
        self.transaction = self.isolation = None
        self.trace_id = self.event_id = None
        self.start = time.perf_counter()

    def begin(self):
        if not _client: return
        self.isolation = sentry_sdk.isolation_scope()
        scope = self.isolation.__enter__()
        scope.set_client(_client)
        self.transaction = sentry_sdk.start_transaction(name="patchpitch.generate", op="function", source="custom")
        self.transaction.__enter__()
        self.trace_id = self.transaction.trace_id
        for key, value in [("patchpitch.format", self.format), ("patchpitch.scenario", self.scenario)]:
            scope.set_tag(key, value)
            self.transaction.set_tag(key, value)
        self.transaction.set_status("ok")

    @contextmanager
    def span(self, kind, model=None):
        span = None
        if self.transaction:
            op = "gen_ai.chat" if kind == "ollama" else "validation"
            model = _model(model)
            span = _attempt(self.transaction.start_child, op=op, name=f"chat {model}" if model else "validate draft")
        observed = ObservedSpan(span)
        if kind == "ollama":
            for key, value in [("gen_ai.operation.name", "chat"), ("gen_ai.provider.name", "ollama"), ("gen_ai.request.model", model)]: observed.data(key, value)
        if span: _attempt(span.set_status, "ok")
        try:
            yield observed
        except Exception as exc:
            if span:
                code = getattr(exc, "code", "unexpected_error")
                _attempt(span.set_status, "internal_error")
                observed.data("error.type", code if code in ERROR_CODES else "unexpected_error")
            raise
        finally:
            if span: _attempt(span.finish)

    def error(self, code):
        if not self.transaction: return
        code = code if code in ERROR_CODES else "unexpected_error"
        _attempt(self.transaction.set_status, "internal_error")
        _attempt(self.transaction.set_tag, "error.code", code)
        self.event_id = _attempt(sentry_sdk.capture_event, {"level": "error", "tags":{
            "error.code":code, "patchpitch.format":self.format, "patchpitch.scenario":self.scenario}})

    def close(self):
        if self.transaction:
            _attempt(self.transaction.set_data, "patchpitch.duration_ms", (time.perf_counter()-self.start)*1000)
            _attempt(self.transaction.__exit__, None, None, None)
        if self.isolation: _attempt(self.isolation.__exit__, None, None, None)


@contextmanager
def generation(format, scenario="LIVE_MODEL"):
    run = Generation(format, scenario)
    _attempt(run.begin)
    try:
        yield run
    finally:
        run.close()
