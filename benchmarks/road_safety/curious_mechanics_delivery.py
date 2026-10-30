"""Controller verifies/exports; GitHub encodes. No native renderer or publisher."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from PIL import Image,ImageStat,ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import episode2_film as film
from shorts_studio.factory import curious_mechanics_timeline as timeline
from shorts_studio.factory.curious_mechanics_native_qa import verify
ROOT=Path(__file__).resolve().parents[2]
LEGACY='e6f3da8e73bbcecc54454b4d3a7407d4e7949ac93689a49eb289f123772dd797'
FIXED='700c523fac79cbafac3e763e0e9bbace429c6deff89da1ddbf97616f143debae'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def validate_layout(shards,canonical,variant):
    ordered=sorted(shards,key=lambda x:x['proof']['first_frame']);proofs=[x['proof'] for x in ordered];film.validate_shard_layout(proofs)
    hashes=[]
    for s in ordered:
        p=s['proof'];assert p['episode_id']=='curious-mechanics-'+variant
        assert p['renderer_source_sha256'] in (LEGACY,FIXED)
        assert p['renderer']=='CYCLES' and p['cycles_samples']==32 and p['resolution']==[1080,1920] and p['fps']==30 and p['preview_only'] is False
        assert p['car_mesh_parts']>=65 and p['rotating_wheel_pivots']==4 and p['physically_calibrated'] is False and p['upload_ready'] is False
        assert s['controller_qa']['status']=='PASS_NATIVE_ORIGINAL_SHARD' and s['controller_qa']['frames']==p['frames']
        assert len(s['rgb_md5'])==p['frames']
        assert all(canonical[k]==c for k,c in p['camera_by_shot'].items()),'CAMERA_RESET'
        hashes.extend(s['rgb_md5'])
    assert len(hashes)==len(set(hashes))==900,'CLONED_NATIVE_PIXELS'
    return ordered

def export(a):
    plan=json.loads(a.plan.read_text());assert plan['status']=='CORRECTED_FULL_NATIVE_READY_ASSEMBLY';a.out.mkdir(parents=True,exist_ok=True);(a.out/'clips').mkdir(exist_ok=True);(a.out/'audio').mkdir(exist_ok=True)
    fonts=a.out/'fonts';fonts.mkdir(exist_ok=True);shutil.copyfile('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',fonts/'DejaVuSans.ttf')
    source=a.plan.parent;canonical=plan['canonical_camera_by_shot'];assert digest(a.legacy_renderer)==LEGACY;assert digest(ROOT/'benchmarks/road_safety/render_curious_mechanics.py')==FIXED
    for v in 'ABC':
        shards=[]
        for row in sorted((x for x in plan['selected_shards'] if x['variant']==v),key=lambda x:x['start']):
            d=Path(row['directory']);p=json.loads((d/'episode-proof.json').read_text());renderer=a.legacy_renderer if p['renderer_source_sha256']==LEGACY else ROOT/'benchmarks/road_safety/render_curious_mechanics.py';manifest=ROOT/f'examples/experiments/curious-mechanics-{v}.json';qa=verify(d,manifest,renderer)
            clip=d/'native-lossless.mkv';assert digest(clip)==row['clip_sha256'];rgb=[]
            for n in p['frame_numbers']:
                with Image.open(d/f'frame_{n:04d}.png') as im:rgb.append(hashlib.md5(im.convert('RGB').tobytes()).hexdigest())
            target=Path('clips')/f'{v}-{row["start"]:04d}.mkv';dest=a.out/target
            if dest.exists():assert digest(dest)==row['clip_sha256']
            else:os.link(clip,dest)
            shards.append(dict(clip=str(target),clip_sha256=row['clip_sha256'],rgb_md5=rgb,proof=p,controller_qa=qa,validator_sha256=digest(ROOT/'shorts_studio/factory/curious_mechanics_native_qa.py')))
            print('EXPORT_NATIVE_QA',v,row['start'],flush=True)
        shards=validate_layout(shards,canonical,v);audio=source/'audio-final'/v;audio_meta=json.loads((audio/'audio-validation.json').read_text());assert audio_meta['status']=='PASS' and audio_meta['voice']=='en-US-AndrewNeural' and audio_meta['rate']=='+5%' and digest(audio/'narration.wav')==audio_meta['narration_sha256']
        files={}
        for name in ['narration.wav','film.ass','audio-validation.json']:
            assert digest(audio/name)==plan['audio'][v][name];dest=a.out/'audio'/v/name;dest.parent.mkdir(exist_ok=True)
            if not dest.exists():os.link(audio/name,dest)
            files[name]=dict(path=str(dest.relative_to(a.out)),sha256=digest(dest))
        write(a.out/f'{v}.json',dict(variant=v,shards=shards,canonical_camera_by_shot=canonical,audio=files,controller_png_qa='ACTUALLY_EXECUTED',upload_authorized=False))
    write(a.out/'manifest.json',dict(status='VERIFIED_NATIVE_EXPORT',font_sha256=digest(a.out/'fonts/DejaVuSans.ttf'),files={str(p.relative_to(a.out)):digest(p) for p in a.out.rglob('*.json') if p.name not in ('manifest.json','failure.json')},upload_authorized=False));print('EXPORT_READY',digest(a.out/'manifest.json'),flush=True)

def semantic(final,out,episode,audio):
    from shorts_studio.visual_qa import ClipSemanticVisionProvider
    provider=ClipSemanticVisionProvider();base=timeline.original.load_episode(ROOT/'examples/factory/rumble-episode2-30s.json');by_id={s['id']:s for s in base['shots']};results=[]
    for shot in episode['shots']:
        t=((shot['start']+shot['end'])/2-1)/30;style='_'.join(shot['id'].split('_')[2:]);reference=by_id[style];p=out/f'semantic-{shot["id"]}.png';film.run(['ffmpeg','-v','error','-y','-ss',t,'-i',final,'-frames:v','1',p])
        with Image.open(p) as im:im.convert('RGB').crop((0,0,1080,1400)).save(p)
        beat=next(b for b in audio['beats'] if b['start']<=t<b['end']);verdict=provider.evaluate(str(p),reference['visual_proof'],narration=beat['narration_en'],positive_labels=list(timeline.original.semantic_labels(style)),negative_labels=list(timeline.original.SEMANTIC_NEGATIVE_LABELS),media_box_applied=True);results.append(dict(shot=shot['id'],timestamp=t,**verdict));write(out/'semantic-results.json',results)
    assert all(r['status']=='PASS' for r in results),('SEMANTIC_VISUAL_QA',results)
    return results

def assemble(a):
    meta=json.loads((a.bundle/f'{a.variant}.json').read_text());assert meta['variant']==a.variant and meta['controller_png_qa']=='ACTUALLY_EXECUTED';shards=validate_layout(meta['shards'],meta['canonical_camera_by_shot'],a.variant);a.out.mkdir(parents=True,exist_ok=True)
    for s in shards:
        p=s['proof'];assert s['validator_sha256']==digest(ROOT/'shorts_studio/factory/curious_mechanics_native_qa.py');assert digest(a.bundle/s['clip'])==s['clip_sha256']
        for key,path in [('timeline_source_sha256',ROOT/'shorts_studio/factory/curious_mechanics_timeline.py'),('canonical_timeline_sha256',ROOT/'shorts_studio/factory/rumble_episode2.py'),('manifest_sha256',ROOT/f'examples/experiments/curious-mechanics-{a.variant}.json'),('experiment_plan_sha256',ROOT/'examples/experiments/curious-mechanics-rumble-formats.json')]:assert p[key]==digest(path)
        dec=film.run(['ffmpeg','-v','error','-i',a.bundle/s['clip'],'-pix_fmt','rgb24','-f','framemd5','-']).stdout;actual=[l.split(',')[-1].strip() for l in dec.splitlines() if l and not l.startswith('#')];assert actual==s['rgb_md5'],'EXPORTED_CLIP_PIXEL_MISMATCH'
    for name,rec in meta['audio'].items():assert digest(a.bundle/rec['path'])==rec['sha256'];shutil.copyfile(a.bundle/rec['path'],a.out/name)
    audio=json.loads((a.out/'audio-validation.json').read_text());assert audio['status']=='PASS' and audio['voice']=='en-US-AndrewNeural' and audio['rate']=='+5%';assert digest(a.out/'narration.wav')==audio['narration_sha256']
    font_path=a.bundle/'fonts/DejaVuSans.ttf';assert digest(font_path)==json.loads((a.bundle/'manifest.json').read_text())['font_sha256'];font=ImageFont.truetype(str(font_path),62)
    assert abs(float(film.probe(a.out/'narration.wav')['format']['duration'])-30)<.02
    for cue in audio['cues']:
        assert 0<=cue['start']<cue['end']<=30 and len(cue['text'].replace(r'\N',' '))<=31
        assert all(font.getlength(line)<=900 for line in cue['text'].split(r'\N'))
    assert all(x['end']<=y['start'] for x,y in zip(audio['cues'],audio['cues'][1:]))
    episode=timeline.load_episode(ROOT/f'examples/experiments/curious-mechanics-{a.variant}.json');concat=a.out/'concat.txt';concat.write_text(''.join(f"file '{(a.bundle/s['clip']).resolve()}'\n" for s in shards));final=a.out/f'curious-mechanics-{a.variant}.mp4'
    assert not final.exists(),'Preserve existing output; choose a new assembly directory'
    film.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',concat,'-i',a.out/'narration.wav','-vf',film.caption_filter(a.out)+':fontsdir='+str(a.bundle/'fonts'),'-map','0:v:0','-map','1:a:0','-t','30','-c:v','libx264','-preset','slow','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',final])
    info=film.probe(final);v=next(s for s in info['streams'] if s['codec_type']=='video');au=next(s for s in info['streams'] if s['codec_type']=='audio');assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_read_frames']),v['codec_name'],v['pix_fmt'])==(1080,1920,'30/1',900,'h264','yuv420p');assert au['codec_name']=='aac' and au['sample_rate']=='48000' and au['channels']==1;assert abs(float(info['format']['duration'])-30)<.04
    film.run(['ffmpeg','-v','error','-i',final,'-f','null','-']);md5=film.run(['ffmpeg','-v','error','-i',final,'-map','0:v:0','-f','framemd5','-']).stdout;hashes=[s.split(',')[-1].strip() for s in md5.splitlines() if s and not s.startswith('#')];assert len(hashes)==len(set(hashes))==900
    assert 'black_start:' not in film.run(['ffmpeg','-hide_banner','-i',final,'-vf','blackdetect=d=0.15:pix_th=0.06','-an','-f','null','-']).stderr
    gaps=film.silence(final);levels=film.check_loudness(film.loudness(final));viewer=film.original_video_qa(final,a.out,audio['cues'])
    for i,shot in enumerate(episode['shots']):
        t=((shot['start']+shot['end'])/2-1)/30;p=a.out/f'review-{i:02d}.jpg';film.run(['ffmpeg','-v','error','-y','-ss',t,'-i',final,'-frames:v','1',p])
        with Image.open(p) as im:assert max(im.convert('L').crop((0,1400,1080,1440)).getextrema())<=24;assert ImageStat.Stat(im.convert('L').crop((0,0,1080,1400))).mean[0]>=25
    meaning=semantic(final,a.out,episode,audio);write(a.out/'film-validation.json',dict(technical_status='PASS',sha256=digest(final),frames=900,seconds=30,resolution=[1080,1920],cycles_samples=32,native_input_versions=sorted({s['proof']['renderer_source_sha256'] for s in shards}),source_frames_verified=900,semantic_visual_qa=meaning,original_video_qa=viewer,silence_seconds=gaps,loudness=levels,editorial_status='REQUIRES_ACTUAL_REVIEW',human_first_view='UNVERIFIED',upload_authorized=False));print('FINAL_TECHNICAL_PASS',a.variant,digest(final),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True);e=sub.add_parser('export');e.add_argument('--plan',type=Path,required=True);e.add_argument('--legacy-renderer',type=Path,required=True);e.add_argument('--out',type=Path,required=True);c=sub.add_parser('assemble');c.add_argument('--bundle',type=Path,required=True);c.add_argument('--variant',choices=list('ABC'),required=True);c.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:export(a) if a.mode=='export' else assemble(a)
    except Exception as exc:
        if a.out.exists():write(a.out/'failure.json',dict(status='HOLD',reason=str(exc),upload_authorized=False))
        raise
