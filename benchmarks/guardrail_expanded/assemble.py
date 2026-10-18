"""Expanded English explanation over the exact existing 900 native frames."""
import importlib.util,json,os,re,shutil,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
out=Path(os.environ['FILM_OUT']);out.mkdir(parents=True,exist_ok=True)
film=json.loads((ROOT/'film.json').read_text())
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.film=film;module.out=out
    return module
def speech():
    module=load('expanded_english_speech',ROOT.parent/'guardrail_english/assemble.py')
    module.ROOT=ROOT
    capture=json.loads((ROOT/'narration/capture.json').read_text())
    for rec in capture['shots']:
        raw=ROOT/'narration'/rec['raw_audio']
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==rec['raw_audio_sha256'],'RAW_PROVIDER_HASH_MISMATCH'
        metadata=json.loads((ROOT/'narration'/rec['timing']).read_text())
        last=max(w['end'] for w in metadata['words'])
        assert rec['tail_trim_end_s']>=last+.1,'SPEECH_TAIL_CLIPPED'
        assert float(module.probe(ROOT/'narration'/rec['audio'])['format']['duration'])>=last+.1
    module.make_speech()
def assemble():
    module=load('expanded_native_assembly',ROOT.parent/'guardrail_director/assemble.py')
    proof=json.loads(Path(os.environ['EXPANDED_SOURCE_PROOF']).read_text())
    assert proof['technical_status']=='PASS' and proof['frames']==900
    assert proof['new_native_frames']==570 and proof['reused_native_frames']==330
    module.assemble()
    report=json.loads((out/'director_validation.json').read_text())
    assert report['native_frames']==proof['native_frames'],'NATIVE_FOOTAGE_CHANGED'
    final=out/'guardrail-expanded-english-30s-1080p.mp4'
    shutil.copy2(out/'guardrail-director-english-30s-1080p.mp4',final)
    detection=module.run(['ffmpeg','-hide_banner','-i',str(final),'-af','silencedetect=noise=-35dB:d=0.3','-vn','-f','null','-']).stderr
    gaps=[float(x) for x in re.findall(r'silence_duration:\s*([0-9.]+)',detection)]
    assert max(gaps,default=0)<=.9,('LONG_DEAD_AIR',gaps)
    assert sum(gaps)<=5,('EXCESSIVE_TOTAL_SILENCE',gaps)
    narration=json.loads((out/'narration_validation.json').read_text())
    text=' '.join(s['narration'] for s in film['shots'])
    baseline=json.loads((ROOT.parent/'guardrail_english/film.json').read_text())
    old_count=sum(len(s['narration'].split()) for s in baseline['shots'])
    assert len(text.split())>old_count
    assert narration['status']=='PASS'
    (out/'expanded_validation.json').write_text(json.dumps({
        'status':'PASS','duration':30,'frames':900,'native_source_unchanged':True,
        'source_full_run_id':39111993576,'source_full_head':'d9bd962270da3a7d9afc3054f4c488f0d56b758f',
        'script_words':len(text.split()),'previous_script_words':old_count,
        'audio_speed_change':False,'voice':film['voice'],'rate':film['rate'],
        'silence_detector':'AAC, -35dB, minimum 0.3s',
        'detected_silence_seconds':gaps,'maximum_silence_seconds':max(gaps,default=0),
        'total_detected_silence_seconds':sum(gaps),'upper_overlays':False
    },indent=2))
    (out/'script-en.txt').write_text('\n\n'.join(s['narration'] for s in film['shots'])+'\n')
    print('EXPANDED_30S_900_NATIVE_AND_SILENCE_PASS',gaps,flush=True)
if __name__=='__main__':
    speech() if sys.argv[1]=='speech' else assemble()
