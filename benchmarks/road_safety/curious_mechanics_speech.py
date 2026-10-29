"""Capture existing Andrew voice and real word boundaries; never invent timings."""
import argparse, asyncio, hashlib, json, re, subprocess, shutil
from pathlib import Path
import edge_tts

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
async def capture(plan, out):
    out.mkdir(parents=True, exist_ok=True)
    reports=[]
    cached=list(out.parent.glob("speech-v*/*/beat_*.json"))
    for variant in plan['variants']:
        folder=out/variant['id']; folder.mkdir(exist_ok=True)
        beats=[]
        for i,beat in enumerate(variant['beats'],1):
            audio=folder/f'beat_{i:02}.mp3'; timing=folder/f'beat_{i:02}.json'
            matches=[]
            for candidate in cached:
                rec=json.loads(candidate.read_text())
                raw=candidate.with_suffix('.mp3')
                if rec.get('text')==beat['narration_en'] and rec.get('voice')=='en-US-AndrewNeural' and rec.get('rate')=='+5%' and raw.exists() and sha(raw)==rec['audio_sha256']:
                    matches.append((raw,rec))
            if matches:
                raw,rec=matches[0]
                if raw.resolve()!=audio.resolve(): shutil.copyfile(raw,audio)
                words=rec['words']
            else:
                if audio.exists() or timing.exists(): raise RuntimeError('Unreconciled capture output')
                async def request():
                    words=[];data=bytearray()
                    async for chunk in edge_tts.Communicate(beat['narration_en'], 'en-US-AndrewNeural', rate='+5%', boundary='WordBoundary').stream():
                        if chunk['type']=='audio': data.extend(chunk['data'])
                        elif chunk['type']=='WordBoundary': words.append(dict(text=chunk['text'],start=chunk['offset']/1e7,end=(chunk['offset']+chunk['duration'])/1e7))
                    return data,words
                for attempt in range(2):
                    try:
                        data,words=await asyncio.wait_for(request(),timeout=80);break
                    except (edge_tts.exceptions.NoAudioReceived,asyncio.TimeoutError):
                        if attempt==1: raise
                        await asyncio.sleep(3)
                audio.write_bytes(data)
            duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(audio)],text=True))
            normalize=lambda s:re.sub('[^a-z0-9]','',s.lower())
            assert words and normalize(' '.join(w['text'] for w in words))==normalize(beat['narration_en'])
            assert all(0<=w['start']<w['end']<=duration+.05 for w in words)
            available=beat['end']-beat['start']
            record=dict(text=beat['narration_en'],voice='en-US-AndrewNeural',rate='+5%',words=words,duration=duration,audio_sha256=sha(audio),available_seconds=available,fits=duration<=available-.1)
            timing.write_text(json.dumps(record,indent=2)+'\n');beats.append(record)
            print(variant['id'],i,round(duration,3),'fit',record['fits'],flush=True)
        report=dict(variant=variant['id'],beats=beats,total_speech_seconds=sum(b['duration'] for b in beats),target_seconds=30,production_approved=False)
        (folder/'capture.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
    (out/'capture-summary.json').write_text(json.dumps(reports,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    asyncio.run(capture(json.loads(a.plan.read_text()),a.out))
