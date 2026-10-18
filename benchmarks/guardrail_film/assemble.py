"""Author six-shot narration/subtitles, or assemble and audit the complete film."""
import asyncio, json, os, subprocess, sys
from pathlib import Path
from dataclasses import asdict

ROOT=Path(__file__).resolve().parent
film=json.loads((ROOT/'film.json').read_text())
out=Path(os.environ['FILM_OUT']);out.mkdir(parents=True,exist_ok=True)

def run(args):return subprocess.run(args,check=True,capture_output=True,text=True)
def probe(p):return json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)]).stdout)
def stamp(t):
    n=round(t*100);return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'
def srt_time(t):return '0'+stamp(t).replace('.',',')+'0'

def make_speech():
    from shorts_studio.tts import edge_tts_with_boundaries
    from shorts_studio.timing import validate_timings
    all_cues=[];pieces=[];audio_reports=[]
    for shot in film['shots']:
        i=shot['id'];audio=out/f'voice_{i:02d}.mp3';timing=out/f'voice_{i:02d}.timing.json'
        words=asyncio.run(edge_tts_with_boundaries(shot['narration'],audio,timing))
        duration=float(probe(audio)['format']['duration']);slot=(shot['end']-shot['start']+1)/30
        assert duration<=slot-.25,('NARRATION_TOO_LONG',i,duration,slot)
        validate_timings(words,duration)
        assert words and all(w.text.strip() for w in words)
        offset=(shot['start']-1)/30+.10
        # Small, provider-timed groups. Preserve pauses; never estimate from text length.
        for j in range(0,len(words),3):
            group=words[j:j+3]
            all_cues.append({'start':offset+group[0].start,'end':offset+group[-1].end,'text':' '.join(w.text for w in group),'shot':i})
        wav=out/f'voice_{i:02d}.wav'
        run(['ffmpeg','-v','error','-y','-i',str(audio),'-af',f'adelay=100,apad=whole_dur={slot}','-t',str(slot),'-ar','48000','-ac','1',str(wav)])
        pieces.append(wav)
        audio_reports.append({'shot':i,'duration':duration,'slot':slot,'timing_source':'existing Korean prosody planner / provider boundaries','words':[asdict(w) for w in words]})
    (out/'voice_concat.txt').write_text(''.join(f"file '{p.resolve()}'\n" for p in pieces))
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(out/'voice_concat.txt'),'-af','loudnorm=I=-16:TP=-1.5:LRA=9','-ar','48000','-ac','1',str(out/'narration.wav')])
    assert abs(float(probe(out/'narration.wav')['format']['duration'])-30)<.02
    (out/'narration_validation.json').write_text(json.dumps({'status':'PASS','shots':audio_reports,'cues':all_cues},ensure_ascii=False,indent=2))
    (out/'captions.srt').write_text('\n\n'.join(f"{i}\n{srt_time(q['start'])} --> {srt_time(q['end'])}\n{q['text']}" for i,q in enumerate(all_cues,1))+'\n',encoding='utf-8')
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Noto Sans CJK KR,55,&H00FFFFFF,&H00FFFFFF,&H00201710,&H80201710,-1,0,0,0,100,100,0,0,1,3,1,8,65,65,205,1
Style: Label,Noto Sans CJK KR,34,&H00F0D68B,&H00F0D68B,&H00201710,&H80201710,0,0,0,0,100,100,0,0,1,2,0,8,65,65,293,1
Style: Caption,Noto Sans CJK KR,51,&H00FFFFFF,&H00FFFFFF,&H00130F0B,&H80130F0B,-1,0,0,0,100,100,0,0,1,4,1,2,90,90,325,1
Style: Disclosure,Noto Sans CJK KR,27,&H00DADADA,&H00DADADA,&H00201710,&H80201710,0,0,0,0,100,100,0,0,1,2,0,8,70,70,145,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events=[]
    events.append(f"Dialogue: 0,0:00:00.00,0:00:30.00,Disclosure,,0,0,0,,{film['disclosure']}")
    for shot in film['shots']:
        a=(shot['start']-1)/30;b=shot['end']/30
        for style,key in [('Title','title'),('Label','caption')]:events.append(f"Dialogue: 1,{stamp(a)},{stamp(b)},{style},,0,0,0,,{{\\fad(100,100)}}{shot[key]}")
    for q in all_cues:
        assert q['end']<=30 and q['start']<q['end']
        # Measured CJK line budget: <=16 full-width characters per line.
        text=q['text']
        assert len(text)<=31,('CAPTION_TOO_LONG',text)
        if len(text)>16:
            tokens=text.split();mid=len(tokens)//2;text=' '.join(tokens[:mid])+r'\N'+' '.join(tokens[mid:])
        events.append(f"Dialogue: 2,{stamp(q['start'])},{stamp(q['end'])},Caption,,0,0,0,,{text}")
    (out/'film.ass').write_text(header+'\n'.join(events)+'\n',encoding='utf-8')
    print('NARRATION_AND_CAPTIONS_READY',len(all_cues),flush=True)

def assemble():
    base=out/'base';chunks=out/'chunks'
    base_validation=json.loads((base/'video_validation.json').read_text());assert base_validation['status']=='PASS'
    records=json.loads((base/'frame_validation.json').read_text())['frames']
    for p in sorted(chunks.glob('shard_*.json')):
        r=json.loads(p.read_text());assert r['scene_sha']==film['scene_sha']
        assert all(x['width']==1080 and x['height']==1920 and x['samples']==32 for x in r['frames'])
        records+=r['frames']
    assert [r['frame'] for r in records]==list(range(1,901)),('MISSING_OR_UNORDERED_NATIVE_FRAME',len(records))
    assert len({r['sha256'] for r in records})==900,'DUPLICATE_NATIVE_FRAME'
    files=[base/'guardrail-motion-1080p.mp4']+sorted(chunks.glob('chunk_*.mp4'))
    assert len(files)==28,len(files)
    for p in files:
        pr=probe(p);v=next(s for s in pr['streams'] if s['codec_type']=='video')
        assert (v['width'],v['height'],v['r_frame_rate'],v['codec_name'])==(1080,1920,'30/1','h264')
        assert int(v['nb_read_frames'])==(90 if p==files[0] else 30)
    (out/'video_concat.txt').write_text(''.join(f"file '{p.resolve()}'\n" for p in files))
    run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(out/'video_concat.txt'),'-i',str(out/'narration.wav'),'-vf',f"ass={out/'film.ass'}",'-map','0:v:0','-map','1:a:0','-t','30','-c:v','libx264','-preset','slow','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out/'guardrail-full-30s-1080p.mp4')])
    final=out/'guardrail-full-30s-1080p.mp4';pr=probe(final)
    v=next(s for s in pr['streams'] if s['codec_type']=='video');a=next(s for s in pr['streams'] if s['codec_type']=='audio')
    assert (v['width'],v['height'],v['codec_name'],v['pix_fmt'],v['r_frame_rate'],int(v['nb_read_frames']))==(1080,1920,'h264','yuv420p','30/1',900)
    assert a['codec_name']=='aac' and abs(float(pr['format']['duration'])-30)<.04
    run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
    detection=run(['ffmpeg','-hide_banner','-i',str(final),'-vf','blackdetect=d=0.15:pix_th=0.06','-an','-f','null','-']).stderr
    assert 'black_start:' not in detection,'BLACK_FRAME_RUN'
    (out/'film_validation.json').write_text(json.dumps({'technical_status':'PASS','frames':900,'duration':30,'native_resolution':[1080,1920],'scene_sha':film['scene_sha'],'scene_run_id':film['scene_run_id'],'shots':6,'audio':'Korean narration / AAC','caption_track':'provider-timed','physical_validation':False,'editorial_quality':'REQUIRES_HUMAN_REVIEW','native_frames':records},ensure_ascii=False,indent=2))
    for i,sec in enumerate([.5,2.4,4.3,7.5,9,12.5,15,18,20,23,25.5,28.5]):
        run(['ffmpeg','-v','error','-y','-ss',str(sec),'-i',str(final),'-frames:v','1',str(out/f'film_review_{i:02d}.jpg')])
    print('FULL_30_SECOND_NATIVE_FILM_TECHNICAL_PASS',flush=True)

if __name__=='__main__':
    make_speech() if sys.argv[1]=='speech' else assemble()
