"""Evidence tool mode boundaries; no live Sentry or Ollama requests."""
import json

import pytest

from scripts.sentry_check import run_check
from patchpitch import generator, telemetry


def test_offline_check_never_calls_model_or_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline audit attempted inference or HTTP")
    monkeypatch.setattr(generator, "ollama_json", forbidden)
    monkeypatch.setattr("sentry_sdk.transport.HttpTransport._request", forbidden)
    output = tmp_path / "offline"
    result = run_check(output)
    assert result["status"] == "PASSED" and result["live_model"] == "NOT_RUN"
    assert result["delivery"] == "OFFLINE_NO_NETWORK" and not result["http"]
    assert result["controlled_error_code"] == "invalid_draft"
    assert json.loads((output / "report.json").read_text())["status"] == "PASSED"
    with pytest.raises(FileExistsError):
        run_check(output)


def test_live_check_missing_dsn_retains_failure_without_model_call(tmp_path, monkeypatch):
    monkeypatch.delenv("PATCHPITCH_SENTRY_DSN", raising=False)
    monkeypatch.setattr(generator, "generate", lambda *args: pytest.fail("Missing DSN started inference"))
    output = tmp_path / "missing-dsn"
    result = run_check(output, live=True)
    assert result["status"] == "FAILED" and result["failure"] == "missing_explicit_dsn"
    assert result["live_model"] == "NOT_RUN" and (output / "report.json").exists()
    assert not telemetry.enabled()
