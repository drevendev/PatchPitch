"""Decode the real recording and final film; detect the known gray resize artifact."""
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def inspect(path,ffmpeg):
    width,height,fps=160,90,30
    command=[str(ffmpeg),"-v","error","-i",str(path),"-vf",f"fps={fps},scale={width}:{height}","-an","-f","rawvideo","-pix_fmt","rgb24","-"]
    frames=0; bad=[]
    with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
        while True:
            pixels=process.stdout.read(width*height*3)
            if not pixels:break
            assert len(pixels)==width*height*3,"Partial decoded frame"
            frame=np.frombuffer(pixels,np.uint8).reshape(height,width,3)
            region=frame[:int(height*.85),int(width*.8):].astype(int)
            neutral=(region.max(2)-region.min(2)<5)&(region.mean(2)>95)&(region.mean(2)<175)
            if neutral.mean()>.92:bad.append(round(frames/fps,3))
            frames+=1
        errors=process.stderr.read().decode(errors="replace")
        code=process.wait()
    assert code==0 and not errors,errors
    return {"path":str(path.relative_to(ROOT)),"decoded_frames":frames,"seconds":round(frames/fps,3),"decode_errors":errors,"known_gray_resize_frames":bad,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    ffmpeg=next((ROOT/".tools/ffmpeg").glob("**/bin/ffmpeg.exe"))
    names=["raw-demo.webm","patchpitch-demo.mp4"]
    if (ROOT/"artifacts/review-demo.webm").exists():names.append("review-demo.webm")
    results=[inspect(ROOT/"artifacts"/name,ffmpeg) for name in names]
    report={"kind":"FULL_DECODE_AND_KNOWN_ARTIFACT_CHECK","status":"PASSED" if all(not r["known_gray_resize_frames"] for r in results) else "FAILED","gray_detection":"Right fifth of frame almost entirely neutral gray, RGB mean 95-175; targets the reproduced full-page capture resize defect only.","results":results,"semantic_or_general_visual_quality_guarantee":False}
    (ROOT/"submission/motion-check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    assert report["status"]=="PASSED","Gray resize artifact remains"


if __name__=="__main__":main()
