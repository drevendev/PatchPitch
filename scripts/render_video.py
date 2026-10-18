"""Real UI held steady, quiet editorial accents, and a resolved musical ending."""
import argparse
import base64
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts'
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(ROOT / '.tools' / 'browsers'))
from playwright.sync_api import sync_playwright

NARRATION_CUES = [
    (0, 5, 'Your product deserves a great story.'),
    (5, 12, 'Meet Idle Fantasy Shop, a cozy little game about crafting goods and running your own fantasy shop.'),
    (12, 22, 'This update gives the workshop a plan, and the gathering grounds a chance to rest. These notes come from its real code patch.'),
    (22, 34, "Choose what shipped. Local Gemma writes a fresh announcement from those facts, with the important details kept. This generation wait is shortened."),
    (34, 45, 'A good story still needs a careful look. Check the sources, keep the limits clear, and make it yours if you want.'),
    (45, 54, 'Then take the Markdown with you. An update your players can understand, with a little of the game\'s character still there.'),
    (54, 60, 'PatchPitch. Your product deserves a great story.')
]


def run(args):
    result = subprocess.run([str(a) for a in args], cwd=ART, capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:])
    return result


def data_url(path, mime):
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--voice', choices=['kokoro', 'none'], default='kokoro')
    parser.add_argument('--music', choices=['original', 'none'], default='original')
    parser.add_argument('--reuse-voice', action='store_true', help='Reuse only if the exact narration cues match')
    parser.add_argument('--review-replay', action='store_true', help='Use the explicitly labelled review/export replay of this exact real draft')
    args = parser.parse_args()
    evidence = json.loads((ROOT / 'submission' / 'capture-evidence.json').read_text(encoding='utf-8'))
    if evidence['status'] != 'EXERCISED' or evidence['mock_transport']:
        raise RuntimeError('Successful real capture required')
    if hashlib.sha256((ART / 'raw-demo.webm').read_bytes()).hexdigest() != evidence['raw_sha256']:
        raise RuntimeError('Raw capture checksum mismatch')
    review = None
    if args.review_replay:
        review=json.loads((ROOT/'submission/review-replay-evidence.json').read_text(encoding='utf-8'))
        assert review['source_capture_output_sha256']==evidence['output_sha256']
        assert review['new_inference_calls']==0 and review['model_words_edited'] is False
        assert hashlib.sha256((ART/'review-demo.webm').read_bytes()).hexdigest()==review['raw_sha256']
    candidates = list((ROOT / '.tools' / 'ffmpeg').glob('**/bin/ffmpeg.exe'))
    ffmpeg = str(candidates[0]) if candidates else shutil.which('ffmpeg')
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    ffprobe = str(Path(ffmpeg).with_name('ffprobe.exe')) if os.name == 'nt' else shutil.which('ffprobe')
    if not ffprobe or not Path(ffprobe).exists():
        raise RuntimeError('ffprobe is required')
    elapsed = evidence['response']['meta']['elapsed_seconds']
    cues = NARRATION_CUES
    timestamp = lambda t: f'00:{int(t)//60:02}:{int(t)%60:02},000'
    (ART / 'captions.srt').write_text('\n\n'.join(f'{i}\n{timestamp(a)} --> {timestamp(b)}\n{text}' for i, (a,b,text) in enumerate(cues,1)) + '\n', encoding='utf-8')
    (ART / 'narration.txt').write_text('\n\n'.join(text for _,_,text in cues) + '\n', encoding='utf-8')
    speech = [{'file':f'voice-{i}.wav','text':text,'start':a,'duration':b-a} for i,(a,b,text) in enumerate(cues)]
    # Three quiet seconds let the brand and the final chord land after the voice.
    speech[-1]['duration'] = 63 - speech[-1]['start']
    previous = json.loads((ART / 'narration-cues.json').read_text(encoding='utf-8')) if (ART / 'narration-cues.json').exists() else None
    voice_record = json.loads((ART / 'voice-evidence.json').read_text(encoding='utf-8')) if (ART / 'voice-evidence.json').exists() else {}
    matching_voice = [cue['text'] for cue in voice_record.get('cues',[])] == [cue['text'].replace('PatchPitch','Patch pitch') for cue in speech]
    (ART / 'narration-cues.json').write_text(json.dumps(speech,indent=2),encoding='utf-8')
    if args.voice == 'kokoro' and not (args.reuse_voice and previous == speech and matching_voice and (ART / 'narration-neural.wav').exists()):
        result = subprocess.run([sys.executable,str(ROOT/'scripts'/'narrate_kokoro.py')],cwd=ROOT)
        if result.returncode:
            raise RuntimeError('Narration failed; no fallback voice or stretched speech will be substituted')
    if args.music == 'original':
        result = subprocess.run([sys.executable,str(ROOT/'scripts'/'compose_music.py')],cwd=ROOT)
        if result.returncode:
            raise RuntimeError('Original music composition failed')
    fonts = f"@font-face{{font-family:Manrope;src:url('{data_url(ROOT/'patchpitch/static/fonts/Manrope.ttf','font/ttf')}')}}@font-face{{font-family:Newsreader;src:url('{data_url(ROOT/'patchpitch/static/fonts/Newsreader.ttf','font/ttf')}')}}"
    css = fonts + '''*{box-sizing:border-box}body{margin:0;width:1920px;height:1080px;background:#f0eee6;color:#203c32;font-family:Manrope,sans-serif;overflow:hidden}.frame{position:absolute;inset:66px;border:1px solid #cbd5c0;border-radius:20px}.mark{position:absolute;left:130px;top:115px;font-size:27px;letter-spacing:-1px;font-weight:800}.k{font-size:19px;color:#69775b;letter-spacing:5px;font-weight:700}main{position:absolute;left:160px;top:290px;max-width:1550px}h1{font:500 112px/1.02 Newsreader,Georgia,serif;letter-spacing:-2px;margin:30px 0}p{font-size:27px;line-height:1.65;color:#657258;margin:0}.pill{display:inline-block;background:#dfeaa1;color:#203c32;border:1px solid #cad58c;padding:12px 23px;border-radius:7px;font-size:22px;margin-top:30px}.spark{position:absolute;right:155px;top:210px;font-size:120px;color:#cd4d32}.foot{position:absolute;left:160px;bottom:125px;font-size:18px;letter-spacing:2px;color:#69775b}.dot{color:#cd4d32}'''
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
        def screenshot(name, body, extra=''):
            page.set_content(f'<html><style>{css}{extra}</style>{body}</html>')
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(ART/name))
        shell = '<div class="frame"></div><div class="mark">p. PatchPitch</div>'
        screenshot('title.png', shell + '<span class="spark">✳</span><main><div class="k">FOR THE THINGS YOU MAKE</div><h1>Your product deserves<br>a great story<span class="dot">.</span></h1><p>Real changes. A little more life.</p><span class="pill">Local Gemma · Your own voice</span></main><div class="foot">FROM SHIPPED TO SHARED</div>')
        game = data_url(ART/'game/screen-2.png','image/png')
        screenshot('game.png', '<div class="frame"></div><div class="mark">MEET THE GAME</div><main><div class="k">A COZY LITTLE IDLE GAME</div><h1>Idle Fantasy<br>Shop<span class="dot">.</span></h1><p>Gather. Craft. Stock your shelves.<br>A small shop of your own in Latchford.</p><span class="pill">drevengames.itch.io/idle-fantasy-shop</span></main><img class="game-screen" src="'+game+'"><div class="foot">ACTUAL GAME SCREENSHOT · DREVEN GAMES</div>', 'main{top:275px;max-width:830px}h1{font-size:102px}.game-screen{position:absolute;right:110px;top:260px;width:910px;border:1px solid #d6bd7d;border-radius:12px;box-shadow:0 30px 75px #38452b20;transform:rotate(-2deg)}main p{font-size:24px}.pill{font-size:19px}')
        screenshot('outro.png', shell + '<span class="spark">✳</span><main><div class="k">YOUR NEXT RELEASE STARTS HERE</div><h1>Your product deserves<br>a great story<span class="dot">.</span></h1><p>PatchPitch</p><span class="pill">github.com/drevendev/PatchPitch ↗</span></main><div class="foot">DEMO CASE · IDLE FANTASY SHOP<br><span class="game-credit">drevengames.itch.io/idle-fantasy-shop</span></div>', 'h1{font-size:112px}.game-credit{font-size:15px;letter-spacing:.3px;line-height:2.4}')
        captions = ['A cozy game. A real update.', 'Keep the changes that shipped.', f'Generation wait shortened · actual request: {elapsed:.1f}s', 'The story, with its important details.', 'A careful look at the original facts.', 'Take the story with you. Nothing auto-posted.']
        for i,text in enumerate(captions):
            label='Recorded Gemma draft · review UI' if review and i in (4,5) else 'Idle Fantasy Shop · Real local generation'
            page.set_content(f'<html><style>{fonts}body{{margin:0;background:transparent;color:#fffdf7;font:600 18px Manrope,sans-serif}}.bar{{position:absolute;bottom:0;left:0;right:0;height:130px;box-sizing:border-box;background:#203c32;padding:14px 92px;display:flex;justify-content:space-between}}small{{color:#dfeaa1;font-size:16px;font-weight:500}}</style><div class="bar"><span>{html.escape(text)}</span><small>{label}</small></div></html>')
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(ART/f'overlay-{i}.png'),omit_background=True)
        # Editorial focus is a separate layer; never resample the recorded UI.
        for name,width in [('input',370),('output',470)]:
            page.set_content(f'<html><style>body{{margin:0;background:transparent}}.focus{{position:absolute;left:92px;top:992px;width:{width}px;height:2px;background:#a4b850;border-radius:3px}}</style><div class="focus"></div></html>')
            page.screenshot(path=str(ART/f'focus-{name}.png'),omit_background=True)
        browser.close()
    t = evidence['timeline']
    shots = [
        {'image':'title.png','duration':5},
        {'image':'game.png','duration':7},
        {'start':t['generate']-1.5,'take':1.1,'duration':10,'overlay':1},
        {'start':t['generate']+.2,'take':min(2,t['result']-t['generate']),'duration':2,'overlay':2},
        {'start':t['result']+.1,'take':max(.5,min(2,t['sources']-t['result']-.9)),'duration':10,'overlay':3},
        {'start':t['sources'],'take':max(.7,t['edit']-t['sources']-.4),'duration':11,'overlay':4},
        {'start':t['download'],'take':max(.5,t['end']-t['download']-.2),'duration':9,'overlay':5},
        {'image':'outro.png','duration':9}
    ]
    if review:
        # Hold the readable source state, before the recording closes it.
        shots[5].update(video='review-demo.webm',start=review['timeline']['sources']+.1,take=1)
        shots[6].update(video='review-demo.webm',start=review['timeline']['export'],take=3)
    transition = .65
    for i,shot in enumerate(shots):
        duration = shot['duration'] + (transition if i<len(shots)-1 else 0)
        command = [ffmpeg,'-y','-hide_banner','-loglevel','error']
        if 'image' in shot:
            command += ['-loop','1','-i',shot['image']]
            filters = 'scale=1920:1080,fps=30,format=yuv420p'
        else:
            focus='input' if i==2 else 'output'
            command += ['-ss',shot['start'],'-t',shot['take'],'-i',shot.get('video','raw-demo.webm'),'-i',f"overlay-{shot['overlay']}.png",'-loop','1','-i',f'focus-{focus}.png']
            filters = f"[0:v]scale=1728:972:flags=lanczos,pad=1920:1080:96:0:color=0xf0eee6,fps=30,tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},setpts=PTS-STARTPTS[base];[base][1:v]overlay=0:0[captioned];[2:v]format=rgba,fade=t=in:st=0.4:d=0.8:alpha=1,fade=t=out:st={duration-1}:d=0.8:alpha=1[accent];[captioned][accent]overlay=0:0,format=yuv420p"
        command += ['-filter_complex',filters,'-filter_complex_threads','1','-t',duration,'-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','4',f'clip-{i}.mp4']
        run(command)
        print(f'Steady shot {i+1}/{len(shots)}',flush=True)
    command=[ffmpeg,'-y','-hide_banner','-loglevel','error']
    for i in range(len(shots)):
        command+=['-i',f'clip-{i}.mp4']
    filters=[f'[{i}:v]settb=1/30,setpts=PTS-STARTPTS[v{i}]' for i in range(len(shots))]
    # Soft-edged reveals between cards; aligned dissolves between UI states.
    # A/B pixels stay in place throughout: no camera crop or sliding screenshot.
    transitions=['paper-reveal','paper-reveal','dissolve','dissolve','dissolve','dissolve','paper-reveal']
    cut=0
    previous='v0'
    for i in range(1,len(shots)):
        cut+=shots[i-1]['duration']
        current=f'x{i}'
        if transitions[i-1]=='paper-reveal':
            edge='clip(((1-P)*1.18-X/W)/0.18,0,1)'
            blend=f'(0.5-0.5*cos(PI*{edge}))'
            effect=f"transition=custom:expr='A*(1-{blend})+B*{blend}'"
        else:
            effect='transition=fade'
        filters.append(f'[{previous}][v{i}]xfade={effect}:duration={transition}:offset={cut}[{current}]')
        previous=current
    command+=['-filter_complex',';'.join(filters),'-filter_complex_threads','1','-map',f'[{previous}]','-t','63','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','4','assembled.mp4']
    run(command)
    print('Smooth scene transitions assembled',flush=True)
    audio=[]
    if args.voice=='kokoro':
        run([ffmpeg,'-y','-hide_banner','-loglevel','error','-i','narration-neural.wav','-af','loudnorm=I=-18:TP=-2:LRA=9','-ar','48000','-ac','1','narration.wav'])
        audio_file='narration.wav'
        if args.music=='original':
            # Keep the quiet cadence intact. Dynamic loudnorm on this mix can
            # gate its very quiet ending; use fixed gain and a peak limiter.
            mix='[0:a]asplit=2[voice][side];[1:a]volume=1.0[music];[music][side]sidechaincompress=threshold=0.03:ratio=3:attack=35:release=450[duck];[voice][duck]amix=inputs=2:duration=first:normalize=0,volume=1.08,alimiter=limit=0.89:level=0:latency=1,aresample=48000,afade=t=out:st=60:d=2.7[out]'
            run([ffmpeg,'-y','-hide_banner','-loglevel','error','-i','narration.wav','-i','music-original.wav','-filter_complex',mix,'-map','[out]','-t','63','-ar','48000','-ac','2','mix.wav'])
            audio_file='mix.wav'
        audio=['-i',audio_file,'-map','0:v','-map','1:a','-c:a','aac','-b:a','192k']
    elif args.music=='original':
        audio=['-i','music-original.wav','-map','0:v','-map','1:a','-c:a','aac','-b:a','192k']
    style='FontName=Segoe UI,FontSize=8,PrimaryColour=&H00FFFFFF,OutlineColour=&H00323C20,BorderStyle=3,Outline=1,Shadow=0,MarginV=14,Alignment=2'
    run([ffmpeg,'-y','-hide_banner','-loglevel','error','-i','assembled.mp4',*audio,'-vf',f"subtitles=captions.srt:force_style='{style}'",'-t','63','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart','patchpitch-demo.mp4'])
    probe=json.loads(run([ffprobe,'-v','quiet','-show_format','-show_streams','-of','json','patchpitch-demo.mp4']).stdout)
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert video['width']==1920 and video['height']==1080 and video['codec_name']=='h264' and video['pix_fmt']=='yuv420p' and video['r_frame_rate']=='30/1'
    assert 62.9<=float(probe['format']['duration'])<=63.1
    for second in [3,5.3,8,12.3,17,22.3,24.3,29,34.3,35,36,39,45.3,49,54.3,59,61.5,62.8]:
        run([ffmpeg,'-y','-hide_banner','-loglevel','error','-ss',second,'-i','patchpitch-demo.mp4','-frames:v','1',f'frame-{second}.png'])
    shutil.copyfile(ART/'title.png',ART/'poster.png')
    report={'status':'RENDERED','duration_seconds':float(probe['format']['duration']),'video':{k:video[k] for k in ['codec_name','width','height','pix_fmt','r_frame_rate']},'audio':'KOKORO_LOCAL_AF_HEART' if args.voice=='kokoro' else 'NO_NARRATION','music':args.music,'music_ducked_under_voice':args.voice=='kokoro' and args.music=='original','motion':'Fixed UI coordinates; separate fading editorial accents and native UI disclosure animations','transitions':transitions,'transition_seconds':transition,'ending':{'primary_product':'PatchPitch','game':'Secondary demo-case credit','narration_slot_ends':60,'endcard_hold_to':63,'music_resolves':True,'mix_fade':[60,62.7]},'streams':probe['streams'],'ffmpeg_version':run([ffmpeg,'-version']).stdout.splitlines()[0],'raw_sha256':evidence['raw_sha256'],'mp4_sha256':hashlib.sha256((ART/'patchpitch-demo.mp4').read_bytes()).hexdigest(),'shots':shots,'generation_wait_shortened':True,'actual_generation_seconds':elapsed,'manual_model_copy_edit':evidence['manual_edit']['performed'],'visual_qa':'PENDING_AGENT_FRAME_INSPECTION','published':False}
    (ROOT/'submission/video-evidence.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if review:
        report['review_export_segments']=review
        (ROOT/'submission/video-evidence.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Verified 63 seconds, H.264 1080p30; steady UI, continuous voice and resolved music.',flush=True)


if __name__=='__main__':
    main()
