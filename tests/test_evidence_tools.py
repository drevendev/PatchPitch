"""Offline clean-output and comparison-identity regressions; no inference/download."""
import copy
import json
import sys

import pytest

from patchpitch import generator
from scripts import bootstrap_local, capture_demo, doctor, evaluate, tune_example


def test_doctor_clean_root_reports_unavailable_without_inference(monkeypatch,tmp_path):
    monkeypatch.setattr(doctor,"ROOT",tmp_path)
    monkeypatch.setattr(sys,"argv",["doctor.py"])
    monkeypatch.setattr(doctor.subprocess,"check_output",lambda *a,**kw:"ffmpeg MOCK\n")
    calls=[]
    def offline(path,*args,**kwargs):
        calls.append(path)
        raise generator.GenerationError("ollama_unavailable","MOCK offline",503)
    monkeypatch.setattr(generator,"ollama_json",offline)
    doctor.main()
    report=json.loads((tmp_path/"submission/environment.json").read_text(encoding="utf-8"))
    assert report["LIVE_MODEL"]=="NOT_RUN" and report["ollama_error"]["code"]=="ollama_unavailable"
    assert calls==["/api/version"]


def test_bootstrap_output_parents_exist_before_network(monkeypatch,tmp_path):
    monkeypatch.setattr(bootstrap_local,"ROOT",tmp_path)
    monkeypatch.setattr(bootstrap_local,"TOOLS",tmp_path/".tools")
    def stop(*args,**kwargs):
        assert (tmp_path/"artifacts").is_dir() and (tmp_path/"submission").is_dir()
        raise RuntimeError("Stop before any download")
    monkeypatch.setattr(bootstrap_local.urllib.request,"urlopen",stop)
    with pytest.raises(RuntimeError,match="before any download"):bootstrap_local.main()


def test_tune_creates_nested_parent_before_input_or_model(monkeypatch,tmp_path):
    monkeypatch.setattr(tune_example,"ROOT",tmp_path)
    monkeypatch.setattr(sys,"argv",["tune_example.py","--name","offline-attempt"])
    with pytest.raises(FileNotFoundError):tune_example.main()
    assert (tmp_path/"artifacts/ifs-comparison").is_dir()


def test_capture_persists_early_failure_in_clean_root(monkeypatch,tmp_path):
    monkeypatch.setattr(capture_demo,"ROOT",tmp_path)
    monkeypatch.setattr(sys,"argv",["capture_demo.py"])
    (tmp_path/"examples").mkdir()
    (tmp_path/"examples/idle-fantasy-shop.provenance.json").write_text("{}",encoding="utf-8")
    def no_browser():raise RuntimeError("MOCK browser unavailable")
    monkeypatch.setattr(capture_demo,"sync_playwright",no_browser)
    with pytest.raises(SystemExit):capture_demo.main()
    report=json.loads((tmp_path/"submission/capture-evidence.json").read_text(encoding="utf-8"))
    assert report["status"]=="FAILED" and report["error"]=="MOCK browser unavailable"
    assert (tmp_path/"artifacts/raw").is_dir()


@pytest.fixture
def identity(monkeypatch):
    model={"name":generator.MODEL,"digest":"test-digest"}
    health={"ollama":"ready","model":generator.MODEL,"digest":"test-digest","options":dict(generator.OPTIONS)}
    monkeypatch.setattr(evaluate,"app_json",lambda *args:health)
    monkeypatch.setattr(generator,"ollama_json",lambda path:{"models":[model]})
    return model,health


@pytest.mark.parametrize("field,value",[("model","another:4b"),("digest","another-digest"),("options",{"temperature":9})])
def test_evaluation_rejects_mismatch_before_inference(identity,field,value):
    identity[1][field]=value
    with pytest.raises(ValueError,match="differ"):evaluate.preflight()


def test_actual_response_model_and_options_control_comparability(identity):
    before=evaluate.preflight()
    actual={"meta":{"model":generator.MODEL,"options":dict(generator.OPTIONS)}}
    assert evaluate.response_identity(actual,"structured",before,copy.deepcopy(before))["configuration_comparable"]
    actual["meta"]["model"]="different:12b"
    assert not evaluate.response_identity(actual,"structured",before,before)["configuration_comparable"]
    actual["meta"]["model"]=generator.MODEL
    actual["meta"]["options"]={}
    assert not evaluate.response_identity(actual,"structured",before,before)["configuration_comparable"]
    after=copy.deepcopy(before);after["local_model"]["digest"]="changed"
    assert not evaluate.response_identity({"model":generator.MODEL},"baseline",before,after)["configuration_comparable"]


def test_evaluation_persists_preflight_failures_without_overwriting_attempts(monkeypatch,tmp_path):
    monkeypatch.setattr(evaluate,"ROOT",tmp_path)
    monkeypatch.setattr(sys,"argv",["evaluate.py","--live"])
    def mismatch():raise ValueError("MOCK settings differ")
    monkeypatch.setattr(evaluate,"preflight",mismatch)
    evaluate.main();evaluate.main()
    report=json.loads((tmp_path/"submission/evaluation-summary.json").read_text(encoding="utf-8"))
    assert report["status"]=="PREFLIGHT_FAILED" and report["results"]==[]
    assert len(list((tmp_path/"artifacts/evaluation").glob("*/summary.json")))==2
