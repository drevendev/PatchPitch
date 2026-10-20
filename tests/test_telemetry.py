"""Real SDK/serialized-envelope checks with an offline transport, never Sentry."""
import copy
import json
import time
from datetime import datetime

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope, Item
from sentry_sdk.transport import Transport

from patchpitch import generator, telemetry
from patchpitch.models import PitchInput


class RecordingTransport(Transport):
    envelopes = []
    fail = False

    def capture_envelope(self, envelope):
        if self.fail: raise OSError("OFFLINE simulated outage")
        self.envelopes.append(envelope)


@pytest.fixture(autouse=True)
def isolated_sdk(monkeypatch):
    telemetry.shutdown()
    monkeypatch.delenv("PATCHPITCH_SENTRY_DSN", raising=False)
    monkeypatch.delenv("PATCHPITCH_SENTRY_RELEASE", raising=False)
    RecordingTransport.envelopes = []
    RecordingTransport.fail = False
    yield
    telemetry.shutdown()


def enable():
    assert telemetry.configure(dsn="https://public@example.invalid/1", transport_type=RecordingTransport)


def mock_model(monkeypatch, draft_data, **metadata):
    raw={"done":True,"model":"returned-model:1","message":{"content":json.dumps(draft_data)},**metadata}
    calls=[]
    def send(*args,**kwargs):
        calls.append(args)
        time.sleep(.005)
        return copy.deepcopy(raw)
    monkeypatch.setattr(generator,"ollama_json",send)
    return calls


def events():
    telemetry.flush()
    return [item.payload.json for e in RecordingTransport.envelopes for item in e.items]


def test_missing_or_invalid_dsn_does_not_initialize_or_break_generation(monkeypatch,input_data,draft_data):
    monkeypatch.setenv("SENTRY_DSN","https://unrelated@example.invalid/7")
    assert not telemetry.configure()
    mock_model(monkeypatch,draft_data)
    assert generator.generate(PitchInput.model_validate(input_data))["raw_draft"]==draft_data
    assert not RecordingTransport.envelopes
    assert not telemetry.configure(dsn="INVALID DSN")
    assert generator.generate(PitchInput.model_validate(input_data))["raw_draft"]==draft_data


def test_sdk_configuration_disables_automatic_collection():
    enable();options=telemetry._client.options
    for key in ["default_integrations","auto_enabling_integrations","send_default_pii",
                "include_local_variables","include_source_context","enable_logs","enable_metrics",
                "auto_session_tracking","send_client_reports"]:
        assert options[key] is False
    assert options["max_request_body_size"]=="never" and not telemetry._client.integrations
    assert options["trace_propagation_targets"]==[] and options["profiles_sample_rate"]==0
    assert options["trace_lifecycle"]=="static" and options["stream_gen_ai_spans"] is False


def test_real_sdk_records_one_actual_model_span_and_validation(monkeypatch,input_data,draft_data):
    enable();calls=mock_model(monkeypatch,draft_data,prompt_eval_count=17,eval_count=9)
    result=generator.generate(PitchInput.model_validate(input_data))
    assert result["raw_draft"]==draft_data and len(calls)==1
    [tx]=events();assert tx["transaction"]=="patchpitch.generate"
    assert tx["tags"]["patchpitch.format"]=="devlog"
    assert tx["contexts"]["trace"]["status"]=="ok"
    model,validation=tx["spans"]
    assert model["op"]=="gen_ai.chat" and validation["op"]=="validation"
    assert model["description"]==f"chat {generator.MODEL}"
    assert model["data"]=={"gen_ai.operation.name":"chat","gen_ai.provider.name":"ollama",
        "gen_ai.request.model":generator.MODEL,"gen_ai.response.model":"returned-model:1",
        "gen_ai.usage.input_tokens":17,"gen_ai.usage.output_tokens":9}
    assert model["timestamp"]>=model["start_timestamp"]
    stamp=lambda value:datetime.fromisoformat(value.replace("Z","+00:00")).timestamp()
    assert stamp(model["timestamp"])-stamp(model["start_timestamp"])>=.003
    # SDK converts wall and monotonic clocks separately; allow sub-ms rounding.
    assert stamp(validation["start_timestamp"])>=stamp(model["timestamp"])-.001


@pytest.mark.parametrize("usage",[{}, {"prompt_eval_count":0,"eval_count":0}, {"prompt_eval_count":"17","eval_count":True}])
def test_missing_identity_or_usage_never_becomes_configured_identity_or_zero(monkeypatch,input_data,draft_data,usage):
    enable()
    raw={"done":True,"message":{"content":json.dumps(draft_data)},**usage}
    monkeypatch.setattr(generator,"ollama_json",lambda *args,**kwargs:raw)
    generator.generate(PitchInput.model_validate(input_data))
    model=events()[0]["spans"][0]["data"]
    assert "gen_ai.response.model" not in model
    if usage.get("eval_count") is not None and type(usage["eval_count"]) is int:
        assert model["gen_ai.usage.output_tokens"]==0 and model["gen_ai.usage.input_tokens"]==0
    else:assert not any(k.startswith("gen_ai.usage") for k in model)


@pytest.mark.parametrize("format",["x_single","x_thread"])
def test_social_traces_never_include_facts_drafts_or_provenance(monkeypatch,format):
    from patchpitch import social
    from patchpitch.fact_packs import prepare_pack,load_pack
    from patchpitch.models import SocialInput
    enable()
    pack=prepare_pack(load_pack("patchpitch"));pack.pop("review_required")
    pack["changes"]=[{k:c[k] for k in ("id","text","include")} for c in pack["changes"]]
    pack.update(format=format,confirmed=True)
    n=5 if format=="x_thread" else 1
    raw={"done":True,"model":"returned-model:1","message":{"content":json.dumps({"posts":[{"text":"A private generated paragraph for review.","source_ids":["C03"]} for _ in range(n)]})}}
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:raw)
    social.generate(SocialInput.model_validate(pack))
    serialized=json.dumps(events())
    assert events()[0]["tags"]["patchpitch.format"]==format
    assert "private generated paragraph" not in serialized
    assert "source_references" not in serialized and "source_url" not in serialized
    assert "selected_changes" not in serialized and "Public workflow" not in serialized


def test_controlled_validation_failure_has_linked_error_and_no_fake_inference(input_data,draft_data):
    enable();request=PitchInput.model_validate(input_data)
    draft_data["intro"]["text"]="TODO private fixture."
    raw={"done":True,"message":{"content":json.dumps(draft_data)}}
    with telemetry.generation(request.format,"CONTROLLED_FAILURE") as run:
        with pytest.raises(generator.GenerationError) as exc:
            with run.span("validation"):generator.validate_response(raw,request,generator.build_payload(request))
        run.error(exc.value.code)
    error,tx=events()
    assert error["message"]=="PatchPitch generation failed: invalid_draft"
    assert error["tags"]["patchpitch.scenario"]=="CONTROLLED_FAILURE"
    assert error["contexts"]["trace"]["trace_id"]==tx["contexts"]["trace"]["trace_id"]==run.trace_id
    assert error["event_id"]==run.event_id
    assert tx["transaction"]=="patchpitch.controlled_failure"
    assert [s["op"] for s in tx["spans"]]==["validation"]
    assert tx["contexts"]["trace"]["status"]=="internal_error"


def test_actual_serialized_transport_contains_no_private_context_or_prose(monkeypatch,input_data,draft_data):
    enable();secret="DELIBERATE_PRIVATE_SENTINEL"
    mock_model(monkeypatch,draft_data)
    with sentry_sdk.isolation_scope() as scope:
        scope.set_user({"email":secret,"id":secret})
        scope.set_extra("changelog",secret)
        scope.set_context("private",{"voice":secret})
        scope.add_breadcrumb({"message":secret})
        generator.generate(PitchInput.model_validate(input_data))
        with telemetry.generation("devlog","CONTROLLED_FAILURE") as run:
            with run.span("validation") as observed:
                observed.span.set_data("gen_ai.input.messages",secret)
                observed.span.set_data("gen_ai.output.messages",secret)
            sentry_sdk.capture_event({"tags":{"error.code":"invalid_draft"},"message":secret,
                "request":{"data":secret},"extra":{"voice":secret},"user":{"email":secret},
                "exception":{"values":[{"value":secret,"stacktrace":{"frames":[{"vars":{"draft":secret}}]}}]}})
    payload=b"\n".join(e.serialize() for e in RecordingTransport.envelopes)
    assert secret.encode() not in payload
    assert input_data["changes"][0]["text"].encode() not in payload
    assert draft_data["intro"]["text"].encode() not in payload
    for event in events():
        assert not {"request","user","extra","breadcrumbs","exception","server_name","modules"}&event.keys()


def test_transport_drops_unknown_envelope_headers_and_attachments():
    enable();secret="PRIVATE_ENVELOPE_SENTINEL"
    envelope=Envelope(headers={"trace":{"user_id":secret},"dsn":secret})
    envelope.add_event({"tags":{"error.code":"timeout"},"message":secret})
    envelope.add_item(Item(payload=secret,type="attachment",filename="private.txt"))
    telemetry._client.transport.capture_envelope(envelope)
    [sent]=RecordingTransport.envelopes
    assert not sent.headers and [i.type for i in sent.items]==["event"]
    assert secret.encode() not in sent.serialize()


def test_outage_and_sdk_failure_do_not_change_success_or_business_error(monkeypatch,input_data,draft_data):
    enable();RecordingTransport.fail=True;mock_model(monkeypatch,draft_data)
    assert generator.generate(PitchInput.model_validate(input_data))["raw_draft"]==draft_data
    monkeypatch.setattr(sentry_sdk,"start_transaction",lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError("SDK failure")))
    assert generator.generate(PitchInput.model_validate(input_data))["raw_draft"]==draft_data
    def timeout(*args,**kwargs):raise generator.GenerationError("timeout","Original timeout")
    monkeypatch.setattr(generator,"ollama_json",timeout)
    with pytest.raises(generator.GenerationError,match="Original timeout"):generator.generate(PitchInput.model_validate(input_data))
