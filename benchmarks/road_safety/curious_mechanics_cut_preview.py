"""A silent cut-order preview from passed native frames, never final-film QA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def build(source, out):
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    out.mkdir(parents=True, exist_ok=False)
    choices = [(1,0,30,'LOCATION'), (121,15,30,'GROOVE PROFILE'),
               (301,10,30,'TIRE CONTACT'), (451,10,30,'BODY VIEW'),
               (871,0,30,'RESPONSE')]
    args=['ffmpeg','-v','error'];filters=[];inputs=[];elapsed=0
    for i,(first,a,b,label) in enumerate(choices):
        folder=source/f'curious-progressive-B-{first}'
        clip=folder/'native-lossless.mkv';receipt=json.loads((folder/'native-validation.json').read_text())
        digest=hashlib.sha256(clip.read_bytes()).hexdigest()
        assert receipt['status']=='PASS_NATIVE_ORIGINAL_SHARD' and receipt['decoded_exact'] and digest==receipt['clip_sha256']
        args+=['-i',str(clip)]
        filters.append(f'[{i}:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[v{i}]')
        inputs.append(dict(first_native_frame=first+a,last_native_frame=first+b-1,clip_sha256=digest,label=label,start=elapsed/30,end=(elapsed+b-a)/30))
        elapsed+=b-a
    filters.append(''.join(f'[v{i}]' for i in range(5))+'concat=n=5:v=1:a=0,drawbox=x=0:y=1440:w=1080:h=480:color=black:t=fill[v]')
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    text=f"[v]drawtext=fontfile={font}:text='5 SHOTS - SILENT PREVIEW':x=70:y=1500:fontsize=44:fontcolor=white,drawtext=fontfile={font}:text='NOT THE FINAL 30 SECOND FILM':x=70:y=1570:fontsize=32:fontcolor=white"
    for row in inputs:
        text+=f",drawtext=fontfile={font}:text='{row['label']}':x=70:y=1680:fontsize=52:fontcolor=white:enable='gte(t,{row['start']})*lt(t,{row['end']})'"
    filters.append(text+'[final]')
    final=out/'curious-mechanics-five-shot-PREVIEW-NOT-FINAL.mp4'
    subprocess.run(args+['-filter_complex',';'.join(filters),'-map','[final]','-an','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(final)],check=True)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(final)]))
    v=info['streams'][0]
    assert len(info['streams'])==1 and (v['width'],v['height'],v['r_frame_rate'],int(v['nb_read_frames']))==(1080,1920,'30/1',elapsed)
    assert abs(float(info['format']['duration'])-elapsed/30)<.04
    (out/'preview-proof.json').write_text(json.dumps(dict(status='PREVIEW_ONLY_NOT_FINAL',frames=elapsed,seconds=elapsed/30,sha256=hashlib.sha256(final.read_bytes()).hexdigest(),source_run=41197516170,source_segments=inputs,has_audio=False,full_film_qa_pass=False,upload_authorized=False),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.source,a.out)
