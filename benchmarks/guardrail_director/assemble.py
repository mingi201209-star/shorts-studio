"""Assemble only genuinely rendered native director frames with measured English captions."""
import json,os,subprocess,sys,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parent
film=json.loads((ROOT/'film.json').read_text())
out=Path(os.environ['FILM_OUT']);out.mkdir(parents=True,exist_ok=True)
def run(args):return subprocess.run(args,check=True,capture_output=True,text=True)
def probe(p):return json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)]).stdout)
def speech():
    source=ROOT.parent/'guardrail_english/assemble.py'
    spec=importlib.util.spec_from_file_location('captured_english',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.film=film
    module.make_speech()
    dialogue=[l for l in (out/'film.ass').read_text().splitlines() if l.startswith('Dialogue:')]
    assert dialogue and all(',Caption,' in l for l in dialogue),'UNREQUESTED_UPPER_TEXT'
def assemble():
    records=[]
    for p in sorted((out/'chunks').glob('shard_*.json')):
        data=json.loads(p.read_text());assert data['scene_sha']==film['scene_sha']
        for row in data['frames']:
            if row['frame']>=571:
                assert 'renderer' not in row and row['samples']==32,'BASELINE_RECORD_DRIFT'
                row['renderer']='CYCLES'
                row['provenance']='native frames from pinned run 39101075134'
        records+=data['frames']
    assert [r['frame'] for r in records]==list(range(1,901)),('MISSING_OR_UNORDERED_FRAMES',len(records))
    assert len({r['sha256'] for r in records})==900,'DUPLICATE_NATIVE_FRAME'
    cameras={}
    for row in records:
        assert [row['width'],row['height']]==[1080,1920]
        assert row['renderer']=='CYCLES' and row['samples']==32,'NATIVE_RENDER_SETTING_REGRESSION'
        if row['frame']<=570:
            if row['shot'] in cameras:assert cameras[row['shot']]==row['camera'],'CAMERA_DRIFT'
            cameras[row['shot']]=row['camera']
            if row['shot'] not in (2,4):assert row['car_bounds'] is not None,'CAR_NOT_AUDITED'
        else:
            assert row['shot'] in (5,6) and row['samples']==32,'UNAPPROVED_REUSED_SHOT'
    files=sorted((out/'chunks').glob('chunk_*.mp4'))
    expected_starts=list(range(1,571,10))+list(range(571,901,30))
    assert [int(p.stem.split('_')[1]) for p in files]==expected_starts,'MISSING_NATIVE_CHUNK'
    for p in files:
        v=next(s for s in probe(p)['streams'] if s['codec_type']=='video')
        expected_frames=10 if int(p.stem.split('_')[1])<=570 else 30
        assert (v['width'],v['height'],v['r_frame_rate'],v['codec_name'],int(v['nb_read_frames']))==(1080,1920,'30/1','h264',expected_frames)
    (out/'concat.txt').write_text(''.join(f"file '{p.resolve()}'\n" for p in files))
    assert abs(float(probe(out/'narration.wav')['format']['duration'])-30)<.02
    dialogue=[l for l in (out/'film.ass').read_text().splitlines() if l.startswith('Dialogue:')]
    assert dialogue and all(',Caption,' in l for l in dialogue),'UNREQUESTED_UPPER_TEXT'
    final=out/'guardrail-director-english-30s-1080p.mp4'
    run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(out/'concat.txt'),'-i',str(out/'narration.wav'),'-vf',f"ass={out/'film.ass'}",'-map','0:v:0','-map','1:a:0','-t','30','-c:v','libx264','-preset','slow','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(final)])
    p=probe(final);v=next(s for s in p['streams'] if s['codec_type']=='video');a=next(s for s in p['streams'] if s['codec_type']=='audio')
    assert (v['width'],v['height'],v['codec_name'],v['pix_fmt'],v['r_frame_rate'],int(v['nb_read_frames']))==(1080,1920,'h264','yuv420p','30/1',900)
    assert a['codec_name']=='aac' and abs(float(p['format']['duration'])-30)<.04
    run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
    detect=run(['ffmpeg','-hide_banner','-i',str(final),'-vf','blackdetect=d=0.15:pix_th=0.06','-an','-f','null','-']).stderr
    assert 'black_start:' not in detect,'BLACK_FRAME_RUN'
    report={'technical_status':'PASS','frames':900,'duration':30,'native_resolution':[1080,1920],'scene_sha':film['scene_sha'],'scene_run_id':film['scene_run_id'],'camera_fixed_per_shot':True,'new_native_frames':570,'reused_native_frames':330,'reused_footage_run_id':39101075134,'upper_overlays':False,'audio':'English narration / AAC','caption_track':'captured provider word boundaries','physical_validation':False,'editorial_quality':'REQUIRES_MANUAL_REVIEW','native_frames':records}
    (out/'director_validation.json').write_text(json.dumps(report,indent=2))
    for i,t in enumerate([.5,1.5,2.7,3.8,6.8,8.5,10.8,13.5,15,18,20,23,25,28]):
        run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(final),'-frames:v','1',str(out/f'director_review_{i:02d}.jpg')])
    print('DIRECTOR_NATIVE_900_FRAME_TECHNICAL_PASS',flush=True)
if __name__=='__main__':
    speech() if sys.argv[1]=='speech' else assemble()
