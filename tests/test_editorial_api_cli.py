"""Local transport and CLI share document operations; no live model or DEV calls."""
import json
import sys

from fastapi.testclient import TestClient

from patchpitch.app import app
from patchpitch.cli import main
from patchpitch import editorial as e
from patchpitch.editorial_api import dispatch
from patchpitch.run_store import read_json, write_json
from test_editorial import workspace, complete


def test_cli_schema_init_status_and_preview(workspace, tmp_path, capsys):
    schema = tmp_path / "schema.json"
    assert main(["schema", "--kind", "editorial-job", "--out", str(schema), "--json"]) == 0
    assert read_json(schema)["properties"]["schema_version"]["const"] == "patchpitch.editorial-job/v1"
    capsys.readouterr()
    assert main(["editorial", "status", "--work", str(workspace), "--json"]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "sources_ready"
    assert main(["editorial", "preview", "--work", str(workspace), "--out", str(tmp_path / "preview"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "exported"


def test_api_and_cli_cas_failures_match(workspace, tmp_path, capsys):
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post("/api/editorial", json={"action": "apply", "work": str(workspace), "mutation": {
        "operation_id": "stale", "expected_revision_id": "R" + "0" * 64, "operations": [{"type": "review_sources"}]}})
    assert response.status_code == 409 and response.json()["error"]["code"] == "REVISION_CONFLICT"
    patch = tmp_path / "stale.json"
    write_json(patch, {"operation_id": "stale", "expected_revision_id": "R" + "0" * 64, "operations": [{"type": "review_sources"}]})
    assert main(["editorial", "apply", "--work", str(workspace), "--patch", str(patch), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "REVISION_CONFLICT"


def test_preview_server_allowlists_only_public_bundle_files(workspace):
    complete(workspace)
    client = TestClient(app, base_url="http://127.0.0.1")
    result = client.post("/api/editorial", json={"action": "preview", "work": str(workspace)}).json()
    response = client.get(result["preview_url"])
    assert response.status_code == 200 and "unsafe-eval" not in response.headers["content-security-policy"]
    prefix = result["preview_url"].removesuffix("preview.html")
    for path in ["inputs/snapshot.json", "manifest.json", "receipts/dev.json", "../manifest.json"]:
        assert client.get(prefix + path).status_code == 404
    assert client.post("/api/editorial", json={"action": "status", "work": str(workspace)}, headers={"Origin": "https://evil.example"}).status_code == 403


def test_no_network_flags_by_coercion_or_malformed_ops(workspace):
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post("/api/editorial", json={"action": "bind-url", "work": str(workspace), "url": "https://dev.to/user/article", "verify": "false"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "ARGUMENT_ERROR"
    before = e.load(workspace)[2].revision_id
    response = client.post("/api/editorial", json={"action": "apply", "work": str(workspace), "mutation": {
        "operation_id": "missing-fields", "expected_revision_id": before, "operations": [{"type": "section"}]}})
    assert response.status_code == 422 and response.json()["error"]["code"] == "MUTATION_INVALID"
    assert e.load(workspace)[2].revision_id == before
