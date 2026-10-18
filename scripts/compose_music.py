"""An original, quiet 72-BPM instrumental bed. No samples or external service."""
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    rate, seconds, bpm = 48000, 63, 72
    audio = np.zeros((rate * seconds, 2), dtype=np.float64)
    beat = 60 / bpm
    # Original voicings: Dmaj9, Bm7, Gmaj9, Asus2. Slow, open and unobtrusive.
    chords = [(50, 57, 61, 64, 69), (47, 54, 57, 62, 66),
              (43, 50, 54, 57, 62), (45, 52, 57, 59, 64)]

    def note(midi, start, duration, level, pan, attack, decay=None):
        begin = int(start * rate)
        length = min(int(duration * rate), len(audio) - begin)
        if length <= 0:
            return
        t = np.arange(length) / rate
        hz = 440 * 2 ** ((midi - 69) / 12)
        envelope = (1 - np.exp(-t / attack)) * np.minimum(1, (duration - t) / 1.3)
        if decay:
            envelope *= np.exp(-t / decay)
        tone = np.sin(2 * np.pi * hz * t)
        tone += .17 * np.sin(2 * np.pi * hz * 2 * t)
        tone += .035 * np.sin(2 * np.pi * hz * 3 * t)
        signal = tone * envelope * level
        gains = (np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2))
        for channel, gain in enumerate(gains):
            audio[begin:begin + length, channel] += signal * gain

    for bar in range(9):
        start = bar * 8 * beat
        chord = chords[bar % len(chords)]
        for i, midi in enumerate(chord):
            note(midi, start, 8 * beat + 1.5, .014, (i - 2) * .24, .65)
        for step, index in enumerate((2, 3, 4, 3)):
            note(chord[index] + 12, start + (.5 + step * 1.75) * beat,
                 2.8, .025, (-.3 if step % 2 else .3), .025, 1.15)
    # A deliberate dominant-to-tonic cadence under the closing brand card.
    for i,midi in enumerate(chords[3]):
        note(midi, 54, 3.6, .013, (i-2)*.2, .6)
    for i,midi in enumerate((50,57,62,66,69)):
        note(midi, 57.5, 5.2, .016, (i-2)*.2, .6)
    note(81, 59.2, 3.2, .012, .18, .04, 1.3)
    # A small, diffuse stereo tail; no percussion under the narration.
    dry = audio.copy()
    for delay, amount in ((.23, .16), (.47, .09), (.79, .045)):
        samples = int(delay * rate)
        audio[samples:] += dry[:-samples, ::-1] * amount
    ramp = np.minimum(1, np.arange(len(audio)) / (rate * 2.5))
    tail=np.clip((62.7-np.arange(len(audio))/rate)/3,0,1)
    ramp *= tail*tail*(3-2*tail)
    audio *= ramp[:, None]
    peak = float(np.max(np.abs(audio)))
    target = ROOT / "artifacts" / "music-original.wav"
    sf.write(target, audio, rate, subtype="PCM_24")
    report = {"kind": "ORIGINAL_PROCEDURAL_COMPOSITION", "seconds": seconds,
              "bpm": bpm, "sample_rate": rate, "peak": peak,
              "external_samples": False, "external_inference": False,
              "new_payments": 0, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
              "description": "Soft keys and slow open chords; dominant-to-tonic ending, three-second release and 0.3-second silence.",
              "closing_cadence_seconds": [54,57.5], "fade_to_silence_seconds":62.7}
    (target.parent / "music-evidence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
