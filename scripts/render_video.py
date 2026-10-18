"""Edit real capture into a 63-second demo. Local FFmpeg; no generated UI."""
import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"artifacts"
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/".tools"/"browsers"))
from playwright.sync_api import sync_playwright

NARRATION_CUES=[
    (0,5,"Your product deserves a great story."),
    (5,12,"You shipped the update. Now you need to tell your players what changed."),
    (12,22,"This is Idle Fantasy Shop's real update. Pick the changes that shipped, and leave future plans out."),
    (22,34,"Local Gemma turns those facts into a short announcement. The original wait is shown here, with the pause shortened."),
    (34,45,"Open the source notes. Check the original facts. Then make the final edit in your own words."),
    (45,54,"Copy or download the Markdown. Your draft is ready for review. Nothing is posted automatically."),
    (54,63,"PatchPitch. Built with local Gemma. Small updates. Clear stories.")
]


def run(args):
    result=subprocess.run([str(a) for a in args],cwd=ART,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:])
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--narrate",action="store_true",help="Use an existing local Windows English voice")
    parser.add_argument("--voice",choices=["kokoro","windows","none"],default="kokoro")
    args=parser.parse_args()
    evidence=json.loads((ROOT/"submission"/"capture-evidence.json").read_text(encoding="utf-8"))
    if evidence["status"] != "EXERCISED" or evidence["mock_transport"]:
        raise RuntimeError("A successful real capture is required")
    raw=ART/"raw-demo.webm"
    if hashlib.sha256(raw.read_bytes()).hexdigest() != evidence["raw_sha256"]:
        raise RuntimeError("Raw capture checksum mismatch")
    candidates=list((ROOT/".tools"/"ffmpeg").glob("**/bin/ffmpeg.exe"))
    ffmpeg=str(candidates[0]) if candidates else shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    ffprobe=str(Path(ffmpeg).with_name("ffprobe.exe")) if os.name=="nt" else shutil.which("ffprobe")
    if not ffprobe or not Path(ffprobe).exists():
        raise RuntimeError("ffprobe required for final verification; raw demo remains available")
    elapsed=evidence["response"]["meta"]["elapsed_seconds"]
    cues=NARRATION_CUES
    def timestamp(t): return f"00:{int(t)//60:02}:{int(t)%60:02},000"
    (ART/"captions.srt").write_text("\n\n".join(f"{i}\n{timestamp(start)} --> {timestamp(end)}\n{text}" for i,(start,end,text) in enumerate(cues,1))+"\n",encoding="utf-8")
    (ART/"narration.txt").write_text("\n\n".join(text for _,_,text in cues)+"\n",encoding="utf-8")
    speech=[{"file":f"voice-{i}.wav","text":text,"start":start,"duration":end-start} for i,(start,end,text) in enumerate(cues)]
    (ART/"narration-cues.json").write_text(json.dumps(speech,indent=2),encoding="utf-8")
    voice_status="CAPTIONS_ONLY"
    if args.voice=="kokoro":
        import sys
        narration=subprocess.run([sys.executable,str(ROOT/"scripts"/"narrate_kokoro.py")],capture_output=True,text=True)
        if narration.returncode:raise RuntimeError("Neural narration failed; review the error instead of silently using the old voice:\n"+narration.stderr[-2000:])
        voice_status="KOKORO_LOCAL"
    elif (args.narrate or args.voice=="windows") and os.name=="nt":
        narration=subprocess.run(["powershell.exe","-NoProfile","-File",str(ROOT/"scripts"/"narrate.ps1"),"-ArtifactDirectory",str(ART)],capture_output=True,text=True)
        voice_status="WINDOWS_LOCAL" if narration.returncode==0 else "CAPTIONS_ONLY"
        if narration.returncode: (ART/"voice-error.txt").write_text(narration.stderr,encoding="utf-8")
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":1920,"height":1080},device_scale_factor=1)
        def card(file,kicker,title,sub):
            page.set_content(f"<html><style>body{{margin:0;background:#f7f5ef;color:#172121;font-family:system-ui;display:flex;align-items:center;height:1080px}}main{{margin-left:190px;max-width:1530px}}.k{{color:#d7462f;font-size:24px;font-weight:650;letter-spacing:6px}}h1{{font:normal 96px/1.12 Georgia;letter-spacing:-3px;margin:30px 0}}p{{font-size:28px;color:#6a7067;line-height:1.6}}.dot{{color:#d7462f}}footer{{position:absolute;bottom:150px;font-size:22px;letter-spacing:2px;color:#777e70}}</style><main><div class=k>{html.escape(kicker)}</div><h1>{html.escape(title).replace(chr(10),'<br>')}<span class=dot>.</span></h1><p>{html.escape(sub)}</p><footer>PATCHPITCH / LOCAL WRITING STUDIO</footer></main></html>")
            page.screenshot(path=str(ART/file))
        card("title.png","PATCHPITCH","Your product deserves\na great story","From a short changelog to a draft you can finish.")
        card("outro.png","BUILT WITH LOCAL GEMMA","Small updates.\nClear stories","Review. Edit. Export Markdown.  •  github.com/drevendev/PatchPitch")
        # Transparent editorial overlays, independent of the real application footage.
        captions=["A changelog is not an announcement.","Your changes. Your audience.",f"Generation wait shortened · actual model request: {elapsed:.1f}s","Draft — review before publishing","Your changes. Your audience. Your final edit.","Markdown downloaded. Nothing published."]
        for i,text in enumerate(captions):
            page.set_content(f"<html><style>body{{margin:0;background:transparent;font:600 18px system-ui;color:#fffefa}}.bar{{position:absolute;bottom:0;left:0;right:0;height:144px;background:#172121;padding:10px 90px;box-sizing:border-box;display:flex;justify-content:space-between;align-items:flex-start}}small{{font-size:16px;color:#d7d8ce;font-weight:400}}</style><div class=bar><span>{html.escape(text)}</span><small>Idle Fantasy Shop 0.12 · Real local generation</small></div></html>")
            page.screenshot(path=str(ART/f"overlay-{i}.png"),omit_background=True)
        browser.close()
    timeline=evidence["timeline"]
    # Explicit cuts and held frames; no speed-up of the response itself.
    shots=[
        {"image":"title.png","duration":5},
        {"start":.5,"take":max(.5,timeline["example"]-.5),"duration":7,"overlay":0},
        {"start":timeline["example"],"take":timeline["generate"]-timeline["example"]+.6,"duration":10,"overlay":1},
        {"start":timeline["generate"]+.2,"take":min(2,timeline["result"]-timeline["generate"]),"duration":2,"overlay":2},
        {"start":timeline["result"]+.1,"take":max(.5,timeline["sources"]-timeline["result"]-.1),"duration":10,"overlay":2},
        {"start":timeline["sources"],"take":timeline["download"]-timeline["sources"],"duration":11,"overlay":4},
        {"start":timeline["download"],"take":max(.5,timeline["end"]-timeline["download"]-.2),"duration":9,"overlay":5},
        {"image":"outro.png","duration":9}
    ]
    for i,shot in enumerate(shots):
        command=[ffmpeg,"-y","-hide_banner","-loglevel","error"]
        if "image" in shot:
            command += ["-loop","1","-i",shot["image"]]
            filters=f"scale=1920:1080,fps=30,fade=t=in:st=0:d=0.25,fade=t=out:st={shot['duration']-.25}:d=0.25"
        else:
            command += ["-ss",shot["start"],"-t",shot["take"],"-i","raw-demo.webm","-i",f"overlay-{shot['overlay']}.png"]
            filters=f"[0:v]crop=1440:900:240:80,scale=1498:936,pad=1920:1080:211:0:color=0xf7f5ef,fps=30,tpad=stop_mode=clone:stop_duration={shot['duration']},trim=duration={shot['duration']},setpts=PTS-STARTPTS[base];[base][1:v]overlay=0:0,fade=t=in:st=0:d=0.18,fade=t=out:st={shot['duration']-.18}:d=0.18"
        command += ["-filter_complex",filters,"-t",shot["duration"],"-an","-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p","-threads","4",f"clip-{i}.mp4"]
        run(command)
        print(f"Rendered shot {i+1}/{len(shots)}",flush=True)
    (ART/"clips.txt").write_text("\n".join(f"file 'clip-{i}.mp4'" for i in range(len(shots))),encoding="utf-8")
    run([ffmpeg,"-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i","clips.txt","-c","copy","assembled.mp4"])
    audio=[]
    if voice_status=="KOKORO_LOCAL":
        # One continuous PCM timeline, no packet-copy joins or time stretching.
        run([ffmpeg,"-y","-hide_banner","-loglevel","error","-i","narration-neural.wav","-af","loudnorm=I=-18:TP=-2:LRA=9","-ar","48000","-ac","1","narration.wav"])
        audio=["-i","narration.wav","-map","0:v","-map","1:a","-c:a","aac","-b:a","192k"]
    if voice_status=="WINDOWS_LOCAL":
        for i,cue in enumerate(speech):
            info=json.loads(run([ffprobe,"-v","quiet","-show_format","-of","json",cue["file"]]).stdout)
            duration=float(info["format"]["duration"])
            speed=max(1,duration/(cue["duration"]-.6))
            run([ffmpeg,"-y","-hide_banner","-loglevel","error","-i",cue["file"],"-af",f"atempo={speed:.6f},adelay=200|200,apad,atrim=duration={cue['duration']}","-ar","48000","-ac","1",f"audio-{i}.wav"])
        (ART/"audio.txt").write_text("\n".join(f"file 'audio-{i}.wav'" for i in range(len(speech))),encoding="utf-8")
        run([ffmpeg,"-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i","audio.txt","-c","copy","narration.wav"])
        audio=["-i","narration.wav","-map","0:v","-map","1:a","-c:a","aac","-b:a","160k"]
    # Burn readable subtitles; also deliver the separate SRT for accessible hosting.
    # SRT's default ASS resolution is 384×288; these values scale to ~30px/26px at 1080p.
    style="FontName=Segoe UI,FontSize=8,PrimaryColour=&H00FFFFFF,OutlineColour=&H00172121,BorderStyle=3,Outline=1,Shadow=0,MarginV=7,Alignment=2"
    run([ffmpeg,"-y","-hide_banner","-loglevel","error","-i","assembled.mp4",*audio,"-vf",f"subtitles=captions.srt:force_style='{style}'","-t","63","-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p","-threads","4","-movflags","+faststart","patchpitch-demo.mp4"])
    probe=json.loads(run([ffprobe,"-v","quiet","-show_format","-show_streams","-of","json","patchpitch-demo.mp4"]).stdout)
    video=next(s for s in probe["streams"] if s["codec_type"]=="video")
    assert video["width"]==1920 and video["height"]==1080 and video["codec_name"]=="h264" and video["pix_fmt"]=="yuv420p" and video["r_frame_rate"]=="30/1"
    assert 55<=float(probe["format"]["duration"])<=65
    for second in [3,17,29,39,49,59]:
        run([ffmpeg,"-y","-hide_banner","-loglevel","error","-ss",second,"-i","patchpitch-demo.mp4","-frames:v","1",f"frame-{second}.png"])
    shutil.copyfile(ART/"title.png",ART/"poster.png")
    report={"status":"RENDERED","duration_seconds":float(probe["format"]["duration"]),"video":{k:video[k] for k in ["codec_name","width","height","pix_fmt","r_frame_rate"]},"audio":voice_status,"streams":probe["streams"],"ffmpeg_version":run([ffmpeg,"-version"]).stdout.splitlines()[0],"raw_sha256":evidence["raw_sha256"],"mp4_sha256":hashlib.sha256((ART/"patchpitch-demo.mp4").read_bytes()).hexdigest(),"shots":shots,"generation_wait_shortened":True,"actual_generation_seconds":elapsed,"visual_qa":"PENDING_AGENT_FRAME_INSPECTION","published":False}
    (ROOT/"submission"/"video-evidence.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"Verified {report['duration_seconds']}s, 1920×1080 H.264/30fps/yuv420p; {voice_status}")


if __name__ == "__main__":main()
