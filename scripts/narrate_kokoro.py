"""Optional local neural narration. Model downloads stay in ignored .tools/."""
import argparse
import hashlib
import importlib.metadata
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--voice",default="af_heart",choices=["af_heart","af_bella"])
    parser.add_argument("--preview",action="store_true")
    args=parser.parse_args()
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro
    directory=ROOT/".tools"/"kokoro"
    directory.mkdir(exist_ok=True)
    for name in ["kokoro-v1.0.onnx","voices-v1.0.bin"]:
        if not (directory/name).exists():
            urllib.request.urlretrieve(BASE+name,directory/name)
    engine=Kokoro(str(directory/"kokoro-v1.0.onnx"),str(directory/"voices-v1.0.bin"))
    art=ROOT/"artifacts"
    art.mkdir(exist_ok=True)
    if args.preview:
        text="You shipped the update. Now give it a story. Patch pitch turns your real change notes into a draft for the people who play your game. You check the facts, make the final edit, and download the Markdown."
        start=time.perf_counter()
        samples,rate=engine.create(text,voice=args.voice,speed=1.0,lang="en-us")
        sf.write(art/f"voice-preview-{args.voice}.wav",samples,rate,subtype="PCM_16")
        print(json.dumps({"voice":args.voice,"audio_seconds":len(samples)/rate,"render_seconds":time.perf_counter()-start,"peak":float(np.max(np.abs(samples)))}))
        return
    cues=json.loads((art/"narration-cues.json").read_text(encoding="utf-8"))
    segments=[]
    records=[]
    for i,cue in enumerate(cues):
        # Spaces give the brand a clear pronunciation, not a reference voice clone.
        text=cue["text"].replace("PatchPitch","Patch pitch")
        start=time.perf_counter()
        samples,rate=engine.create(text,voice=args.voice,speed=1.0,lang="en-us")
        actual=len(samples)/rate
        slot=cue["duration"]
        if actual > slot-.35:
            raise RuntimeError(f"Narration cue {i} is {actual:.2f}s for a {slot}s slot. Shorten the script; speech will not be cut or stretched.")
        # Five-ms edge fades remove discontinuities; the speech itself is not time-warped.
        fade=min(int(rate*.005),len(samples)//2)
        samples[:fade]*=np.linspace(0,1,fade)
        samples[-fade:]*=np.linspace(1,0,fade)
        padded=np.zeros(int(rate*slot),dtype=np.float32)
        lead=int(rate*.2)
        padded[lead:lead+len(samples)]=samples
        sf.write(art/cue["file"],samples,rate,subtype="PCM_16")
        segments.append(padded)
        records.append({"cue":i,"text":text,"speech_seconds":round(actual,3),"slot_seconds":slot,"render_seconds":round(time.perf_counter()-start,3)})
        print(f"Neural voice cue {i+1}/{len(cues)}: {actual:.2f}s in {slot}s",flush=True)
    narration=np.concatenate(segments)
    sf.write(art/"narration-neural.wav",narration,rate,subtype="PCM_16")
    report={"engine":"Kokoro ONNX","voice":args.voice,"model":"Kokoro-82M v1.0","model_license":"Apache-2.0","runtime_license":"MIT","packages":{name:importlib.metadata.version(name) for name in ["kokoro-onnx","onnxruntime","soundfile"]},"model_sha256":hashlib.sha256((directory/"kokoro-v1.0.onnx").read_bytes()).hexdigest(),"voices_sha256":hashlib.sha256((directory/"voices-v1.0.bin").read_bytes()).hexdigest(),"sample_rate":rate,"duration_seconds":len(narration)/rate,"peak":float(np.max(np.abs(narration))),"clipped_samples":int(np.sum(np.abs(narration)>=1)),"time_stretch":False,"new_payments":0,"external_inference_calls":0,"cues":records,"owner_listening_review":"PENDING"}
    (art/"voice-evidence.json").write_text(json.dumps(report,indent=2),encoding="utf-8")


if __name__=="__main__":main()
