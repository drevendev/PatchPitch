"""Prepare an explicitly recorded static sample, with no inference/localhost code."""
import html
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    evidence=json.loads((ROOT/"submission"/"capture-evidence.json").read_text(encoding="utf-8"))
    if evidence["status"] != "EXERCISED": raise RuntimeError("Real captured output required")
    target=ROOT/"artifacts"/"site"
    target.mkdir(exist_ok=True)
    response=evidence["response"]
    def e(text):return html.escape(text)
    draft=response["draft"]
    changes="".join(f"<li>{e(c['id'])} — {e(c['text'])}{' <em>Excluded from model</em>' if not c['include'] else ''}</li>" for c in evidence["input"]["changes"])
    highlights="".join(f"<li>{e(b['text'])}</li>" for b in draft["highlights"])
    note=f"<p><strong>Note:</strong> {e(draft['note']['text'])}</p>" if draft["note"] else ""
    document=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PatchPitch — recorded sample</title><link rel="stylesheet" href="style.css"></head><body><main><div class="sample">SAMPLE — recorded local generation · no public inference</div><header><p>PATCHPITCH</p><h1>Your product deserves<br>a great story<span>.</span></h1><p>Turn your changelog into an announcement people understand.</p></header><video controls preload="metadata" poster="poster.png" aria-label="Real PatchPitch demo"><source src="patchpitch-demo.mp4" type="video/mp4"><track default kind="captions" srclang="en" label="English" src="captions.vtt"></video><div class="columns"><section><h2>The original facts</h2><p>Illustrative sample · Pocket Orchard is fictional.</p><p><strong>Audience:</strong> {e(evidence['input']['audience'])}</p><ul>{changes}</ul></section><section><p class="review">Draft — review before publishing</p><h2>{e(draft['title']['text'])}</h2><p>{e(draft['intro']['text'])}</p><ul>{highlights}</ul>{note}<small>{e(response['meta']['model'])} · {response['meta']['elapsed_seconds']:.1f}s actual request · recorded 2026-10-18</small></section></div><details><summary>Source notes</summary><p>Links refer to the generated draft. They are an inspection aid, not a factual guarantee.</p><pre>{e(json.dumps(response['source_map'],indent=2))}</pre></details><section class="run"><h2>Run the real writing workflow locally</h2><p>Python 3.11+ and Ollama with gemma3:4b. Download the approved project source, then:</p><pre>python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
ollama pull gemma3:4b
.venv/Scripts/python.exe -m uvicorn patchpitch.app:app --host 127.0.0.1 --port 8000</pre><p>Open http://127.0.0.1:8000 on your own computer. This static page never contacts your localhost.</p><p>Source publication and hosting await owner approval. No public URL is claimed.</p></section><footer>No accounts. Your final edit. Markdown export.</footer></main></body></html>'''
    document=document.replace("Illustrative sample · Pocket Orchard is fictional.","Real published update · Idle Fantasy Shop 0.12 · selected facts")
    document=document.replace("Source publication and hosting await owner approval. No public URL is claimed.","Source: github.com/drevendev/PatchPitch (MIT). This recorded sample and video are local; hosting awaits approval.")
    (target/"index.html").write_text(document.replace("<track default ", "<track "),encoding="utf-8")
    (target/"style.css").write_text("*{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:#172121;font:17px/1.65 system-ui}main{max-width:1160px;margin:auto;padding:36px}.sample{border:1px solid #d7462f;color:#a33826;padding:10px 18px;font-size:13px;border-radius:5px}header{margin:45px 0 30px}header>p:first-child{font-size:12px;letter-spacing:4px;color:#d7462f}h1{font:400 64px/1.12 Georgia;letter-spacing:-2px;margin:16px 0}h1 span{color:#d7462f}header p{color:#686e65}video{width:100%;border:1px solid #deddd2;border-radius:8px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:45px;margin-top:40px}.columns section{padding:28px;background:#fffefa;border:1px solid #e2dfd3;border-radius:6px}h2{font:400 30px/1.3 Georgia}li{margin:14px 0}ul{padding-left:22px}em{display:block;font-size:12px;color:#a75e38}.review,small{font-size:12px;color:#9d4d37}pre{white-space:pre-wrap;font-size:13px;overflow-wrap:anywhere;background:#ebe9df;padding:18px;border-radius:5px}details,.run{margin:35px 0}summary{cursor:pointer}footer{border-top:1px solid #deddd2;padding:25px 0;color:#74796c;font-size:13px}@media(max-width:700px){main{padding:22px}h1{font-size:42px}.columns{grid-template-columns:1fr;gap:20px}}",encoding="utf-8")
    for file in ["patchpitch-demo.mp4","poster.png"]:
        shutil.copyfile(ROOT/"artifacts"/file,target/file)
    srt=(ROOT/"artifacts"/"captions.srt").read_text(encoding="utf-8")
    (target/"captions.vtt").write_text("WEBVTT\n\n"+srt.replace(",000",".000"),encoding="utf-8")
    (target/"recorded-sample.json").write_text(json.dumps({"kind":"RECORDED_SAMPLE","input":evidence["input"],"response":response,"input_sha256":evidence["input_sha256"],"output_sha256":evidence["output_sha256"]},indent=2,ensure_ascii=False),encoding="utf-8")
    print("Prepared artifacts/site. Not deployed. Static HTML/video only.")


if __name__=="__main__":main()
