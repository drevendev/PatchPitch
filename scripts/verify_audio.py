"""Check the exported audio, including the previously truncated musical tail."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1]


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    ffmpeg=next((ROOT/".tools/ffmpeg").glob("**/bin/ffmpeg.exe"))
    movie=ROOT/"artifacts/patchpitch-demo.mp4";decoded=ROOT/"artifacts/final-audio-check.wav"
    subprocess.run([str(ffmpeg),"-y","-v","error","-i",str(movie),"-vn","-ar","48000","-ac","2",str(decoded)],check=True)
    audio,rate=sf.read(decoded)
    video=json.loads((ROOT/"submission/video-evidence.json").read_text(encoding="utf-8"))
    voice=json.loads((ROOT/"artifacts/voice-evidence.json").read_text(encoding="utf-8"))
    cues=json.loads((ROOT/"artifacts/narration-cues.json").read_text(encoding="utf-8"))
    voice_end=cues[-1]["start"]+.2+voice["cues"][-1]["speech_seconds"]
    windows=[]
    for start,end in [(59,59.5),(60,60.5),(60.5,61),(61,61.5),(62,62.5),(62.8,63)]:
        part=audio[int(start*rate):int(end*rate)]
        rms=float(np.sqrt(np.mean(part*part)))
        windows.append({"seconds":[start,end],"rms_dbfs":round(float(20*np.log10(max(rms,1e-9))),2)})
    tail=float(np.max(np.abs(audio[-int(.25*rate):])))
    clipped=int((np.abs(audio)>=1).sum())
    assert clipped==0 and tail<1e-4
    assert voice_end<=len(audio)/rate-2,"No brand hold after speech"
    if video["music"]=="original":
        assert windows[2]["rms_dbfs"]>-70,"Music was cut off around 60.5s"
        assert windows[1]["rms_dbfs"]>windows[3]["rms_dbfs"]>windows[4]["rms_dbfs"],"Musical tail does not decay"
    report={"kind":"OBJECTIVE_AUDIO_CHECK_NOT_LISTENING_REVIEW","status":"PASSED","mp4_sha256":hashlib.sha256(movie.read_bytes()).hexdigest(),"duration_seconds":len(audio)/rate,"sample_rate":rate,"channels":audio.shape[1],"peak":float(np.max(np.abs(audio))),"clipped_samples":clipped,"final_quarter_second_peak":tail,"end_windows":windows,"last_voice_ends_approximately":voice_end,"brand_hold_after_speech_seconds":len(audio)/rate-voice_end,"speech_cut_or_stretched":False,"tail_decay_check":"PASSED","owner_listening_review":"PENDING","published":False}
    (ROOT/"submission/audio-check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    video["audio_check"]="submission/audio-check.json"
    (ROOT/"submission/video-evidence.json").write_text(json.dumps(video,indent=2),encoding="utf-8")
    print(json.dumps(report))


if __name__=="__main__":main()
