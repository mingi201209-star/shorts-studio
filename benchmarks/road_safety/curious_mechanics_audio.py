"""Lock real captured audio into 30 seconds, with measured captions and old QA."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import ImageFont
from benchmarks.road_safety.episode2_film import run,probe,silence,loudness,check_loudness,stamp
from shorts_studio.factory.rumble_episode2 import caption_groups

def build(capture,out):
 out.mkdir(parents=True,exist_ok=True); (out/'audio-validation.json').unlink(missing_ok=True); report=json.loads((capture/'capture.json').read_text());beats=report['beats']
 slack=(30-sum(b['duration'] for b in beats))/6
 if slack<0:raise ValueError('Narration exceeds 30 seconds; edit text, never time stretch')
 cues=[];pieces=[];cursor=0;locked=[];font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',62)
 for i,b in enumerate(beats,1):
  raw=capture/f'beat_{i:02}.mp3';assert hashlib.sha256(raw.read_bytes()).hexdigest()==b['audio_sha256']
  words=b['words'];tokens=b['text'].split();assert len(words)==len(tokens),'No invented/interpolated word timing'
  window=b['duration']+slack;end=30 if i==6 else cursor+window
  for j,k in caption_groups(b['text']):
   group=words[j:k];text=' '.join(tokens[j:k]);assert len(text)<=31
   if len(text)>24:
    parts=text.split();text=' '.join(parts[:len(parts)//2])+r'\N'+' '.join(parts[len(parts)//2:])
   assert all(font.getlength(line)<=900 for line in text.split(r'\N'))
   cues.append(dict(start=cursor+group[0]['start'],end=cursor+group[-1]['end'],text=text))
  wav=out/f'voice_{i:02}.wav'
  run(['ffmpeg','-v','error','-y','-i',raw,'-af',f'apad=whole_dur={end-cursor:.9f}','-t',f'{end-cursor:.9f}','-ar','48000','-ac','1',wav]);pieces.append(wav)
  locked.append(dict(start=cursor,end=end,narration_en=b['text'],source_audio_sha256=b['audio_sha256']));cursor=end
 concat=out/'voice-concat.txt';concat.write_text(''.join(f"file '{p.resolve()}'\n" for p in pieces))
 run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',concat,'-af','loudnorm=I=-16:TP=-1.5:LRA=9','-ar','48000','-ac','1','-t','30',out/'narration.wav'])
 run(['ffmpeg','-v','error','-y','-i',out/'narration.wav','-c:a','aac','-b:a','192k',out/'audio-preflight.m4a'])
 gaps=silence(out/'audio-preflight.m4a');levels=check_loudness(loudness(out/'audio-preflight.m4a'))
 assert abs(float(probe(out/'narration.wav')['format']['duration'])-30)<.02
 header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,90,90,210,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
 (out/'film.ass').write_text(header+''.join(f"Dialogue: 0,{stamp(c['start'])},{stamp(c['end'])},Caption,,0,0,0,,{c['text']}\n" for c in cues))
 result=dict(status='PASS',voice='en-US-AndrewNeural',rate='+5%',seconds=30,cues=cues,beats=locked,silence_gaps=gaps,loudness=levels,production_approved=False,narration_sha256=hashlib.sha256((out/'narration.wav').read_bytes()).hexdigest())
 (out/'audio-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(report['variant'],'AUDIO_QA_PASS',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.capture,a.out)
