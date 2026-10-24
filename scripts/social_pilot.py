"""Opt-in real browser -> local app -> Gemma -> review/edit/copy/download.

One call per selected case; never retries. Every attempt has a fresh directory.
It cannot mark owner acceptance or X composer verification as complete.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools"/"browsers"))
from patchpitch.social_count import estimate
from patchpitch.build import source_hash

CASES={
    "patchpitch-single":("patchpitch","x_single","show_result"),
    "patchpitch-thread":("patchpitch","x_thread","build_story"),
    "idle-shop":("idle-fantasy-shop","x_single","release"),
}


def write_json(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def source_identity():
    sha=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    paths=subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard"],cwd=ROOT,text=True).splitlines()
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths if (ROOT/p).is_file()}
    return {"head_sha":sha,"worktree_dirty":bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip()),
            "source_tree_sha256":hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),"files":files}


def run_case(page,base,name,out,edit_file=None,interactive_review=False):
    pack,fmt,intent=CASES[name]
    output=out/name/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid4().hex[:8])
    output.mkdir(parents=True,exist_ok=False)
    record={"scenario":"LIVE_MODEL","case":name,"started_at":datetime.now(timezone.utc).isoformat(),
            "owner_acceptance":"NOT_RUN","x_composer_preview":"NOT_RUN","source":source_identity(),
            "environment":{"python":sys.version,"os":platform.platform()},"attempt_directory":str(output.relative_to(ROOT))}
    response_data=None
    def capture(response):
        nonlocal response_data
        if response.url==base+"/api/social":
            record["http_status"]=response.status
            write_json(output/"input.json",response.request.post_data_json)
            response_data=response.json()
            write_json(output/"app-response.json",response_data)
            if "raw_response" in response_data:write_json(output/"raw-response.json",response_data["raw_response"])
            elif response_data.get("evidence",{}).get("raw_response") is not None:
                write_json(output/"raw-response.json",response_data["evidence"]["raw_response"])
    page.on("response",capture)
    try:
        record["health_before"]=page.request.get(base+"/api/health").json()
        if record["health_before"].get("ollama")!="ready":raise RuntimeError("Local Ollama/model not ready.")
        if record["health_before"].get("runtime_source_sha256")!=source_hash():raise RuntimeError("Restart PatchPitch: running source identity differs from this checkout.")
        if record["health_before"].get("sentry_enabled"):raise RuntimeError("Pilot expects Sentry off; do not transmit diagnostics.")
        page.locator("#fact-pack").select_option(pack);page.locator("#load-pack").click()
        page.wait_for_function("() => !busy && document.getElementById('product').value.length>0")
        page.locator("#format").select_option(fmt);page.locator("#intent").select_option(intent)
        # This historical 0.2 pilot intentionally preserves its accepted tag-free
        # inputs. New six-tag campaigns use the 0.3 catalog workflow.
        if page.locator("#legacy-x").count():
            page.locator("#x-tags-tools > summary").click()
            page.locator("#legacy-x").check()
            page.locator("#x-tags-tools > summary").click()
        page.locator("#style").select_option("clear")
        page.locator("#confirmed").check()
        with page.expect_response(lambda r:r.url==base+"/api/social",timeout=650000) as response:
            page.locator("#generate").click()
        page.wait_for_function("() => !busy",timeout=10000)
        if not response.value.ok:raise RuntimeError(str(response_data.get("error",{"code":"invalid_response"})))
        page.locator(".social-card").first.wait_for()
        generated=page.locator(".social-text").evaluate_all("els=>els.map(e=>e.value)")
        write_json(output/"generated-posts.json",generated)
        (output/"generated.txt").write_text("\n\n---\n\n".join(generated)+"\n",encoding="utf-8")
        edits=None
        if interactive_review:
            print("REVIEW "+json.dumps({"case":name,"generated_posts":generated,"app_warnings":response_data.get("warnings",[])},ensure_ascii=False),flush=True)
            start_review=time.perf_counter()
            line=input("Final JSON array of post texts, or empty to keep unchanged: ")
            record["operator_review_seconds"]=round(time.perf_counter()-start_review,3)
            edits=json.loads(line) if line.strip() else generated
        elif edit_file:
            edits=json.loads(Path(edit_file).read_text(encoding="utf-8"))
        if edits is not None:
            if len(edits)!=len(generated):raise RuntimeError("Edit file needs exactly one string per post.")
            if not all(isinstance(text,str) and text.strip() and not estimate(text)["over_limit"] for text in edits):raise RuntimeError("Final edits must be nonempty posts within the conservative budget.")
            for i,text in enumerate(edits):page.locator(".social-text").nth(i).fill(text)
        final=page.locator(".social-text").evaluate_all("els=>els.map(e=>e.value)")
        write_json(output/"final-posts.json",final)
        (output/"final.txt").write_text("\n\n---\n\n".join(final)+"\n",encoding="utf-8")
        for i,text in enumerate(final):
            page.locator(".social-card").nth(i).get_by_role("button",name="Copy this post",exact=True).click()
            copied=page.evaluate("navigator.clipboard.readText()")
            if copied.replace("\r\n","\n")!=text:raise AssertionError("Clipboard differs from editor.")
        with page.expect_download() as download:page.locator("#download").click()
        download.value.save_as(output/"thread.md")
        record["download_name"]=download.value.suggested_filename
        record["counts"]=[estimate(t) for t in final]
        record["agent_editing"]="unchanged" if final==generated else "explicit interactive review" if interactive_review else "explicit --edit-file"
        record["owner_editing_time_seconds"]=None
        record["clipboard_roundtrip"]="PASS";record["download_roundtrip"]="PASS"
        if (output/"thread.md").read_text(encoding="utf-8")!=page.evaluate("currentMarkdown"):raise AssertionError("Download differs from editor.")
        for width in (1440,390):
            page.set_viewport_size({"width":width,"height":1000})
            page.screenshot(path=str(output/f"studio-{width}.png"),full_page=True)
        record["health_after"]=page.request.get(base+"/api/health").json()
        if record["health_after"].get("runtime_source_sha256")!=source_hash():raise RuntimeError("Runtime source identity changed during the run.")
        before,after=record["health_before"],record["health_after"]
        record["digest_observation"]={"source":"/api/health installed model tags before/after inference; not returned inference digest", "before":before.get("digest"),"after":after.get("digest")}
        if (before.get("model"),before.get("digest"),before.get("options"))!=(after.get("model"),after.get("digest"),after.get("options")):raise RuntimeError("Model configuration changed during the run.")
        record["result"]="PASS_ENGINEERING_REVIEW_PENDING"
    except Exception as exc:
        record["result"]="FAIL";record["failure"]=str(exc)
        try:page.screenshot(path=str(output/"failure.png"),full_page=True)
        except Exception:pass
    finally:
        page.remove_listener("response",capture)
        record["finished_at"]=datetime.now(timezone.utc).isoformat()
        record["hashes"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
        write_json(output/"run.json",record)
        write_json(output/"review.json",{"agent_factual_review":"PENDING","owner_review":"NOT_RUN","x_preview":"NOT_RUN","editing_time_seconds":None})
    return {"case":name,"result":record["result"],"directory":str(output),"failure":record.get("failure")}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true",required=True)
    parser.add_argument("--case",choices=[*CASES,"all"],default="all")
    parser.add_argument("--base-url",default="http://127.0.0.1:8000")
    parser.add_argument("--edit-file",help="Explicit JSON list of final post edits, only for a single case")
    parser.add_argument("--interactive-review",action="store_true",help="Pause after each real response for explicit operator edits; owner acceptance remains separate")
    args=parser.parse_args()
    if args.base_url!="http://127.0.0.1:8000":parser.error("Use the local loopback application at port 8000.")
    if args.edit_file and args.case=="all":parser.error("Select one case for explicit edits.")
    if args.edit_file and args.interactive_review:parser.error("Choose interactive review or edit-file, not both.")
    from playwright.sync_api import sync_playwright
    out=ROOT/"artifacts"/"release-0.2.0"/source_identity()["head_sha"]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(permissions=["clipboard-read","clipboard-write"],viewport={"width":1440,"height":1000})
        page=context.new_page();page.on("dialog",lambda d:d.accept())
        page.goto(args.base_url)
        results=[]
        for name in CASES if args.case=="all" else [args.case]:
            result=run_case(page,args.base_url,name,out,args.edit_file,args.interactive_review)
            results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
        page.wait_for_timeout(100)
        context.close();browser.close()
    return 1 if any(r["result"]=="FAIL" for r in results) else 0


if __name__=="__main__":raise SystemExit(main())
