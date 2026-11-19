import copy,hashlib,json
from pathlib import Path
import pytest
from shorts_studio.factory import curious_mechanics_timeline as m
ROOT=Path(__file__).resolve().parents[1]
MAN=ROOT/'examples/experiments/curious-mechanics-A.json'

def altered(tmp_path,change):
 ref=json.loads(MAN.read_text());raw=json.loads(MAN.with_name(ref['plan_path']).read_text());change(raw)
 plan=tmp_path/ref['plan_path'];plan.write_text(json.dumps(raw));ref['plan_sha256']=hashlib.sha256(plan.read_bytes()).hexdigest()
 out=tmp_path/'A.json';out.write_text(json.dumps(ref));return out

@pytest.mark.parametrize('v',['A','B','C'])
def test_complete_native_story_and_visible_opening(v):
 e=m.load_episode(MAN.with_name(f'curious-mechanics-{v}.json'))
 assert [f for s in e['shots'] for f in range(s['start'],s['end']+1)]==list(range(1,901))
 assert m.detail_stage(e['shots'][0]['id'])=='shoulder_context'
 assert len({m.shot_for_frame(e,f)['id'] for f in range(1,151)})>=3
 assert e['shots'][-1]['id'].endswith('driver_response')
 assert all(m.camera_layout(s)['scale']>=15.5 for s in e['shots'] if m.detail_stage(s['id']) in ('shoulder_context','human_response'))

@pytest.mark.parametrize('key,value',[('fps',24),('samples',7),('resolution',[450,800])])
def test_reduced_quality_rejected(tmp_path,key,value):
 with pytest.raises(ValueError):m.load_episode(altered(tmp_path,lambda d:d['controls'].__setitem__(key,value)))

@pytest.mark.parametrize('flag',['upload_authorized','paid_api','merge_authorized','quality_thresholds_changed','frame_holds_or_interpolation'])
def test_unauthorized_mode_rejected(tmp_path,flag):
 with pytest.raises(ValueError):m.load_episode(altered(tmp_path,lambda d:d['safety'].__setitem__(flag,True)))

def test_tampered_plan_rejected(tmp_path):
 p=altered(tmp_path,lambda d:None);ref=json.loads(p.read_text());p.with_name(ref['plan_path']).write_text('{}')
 with pytest.raises(ValueError,match='binding'):m.load_episode(p)

def test_gapped_audio_rejected(tmp_path):
 with pytest.raises(ValueError):m.load_episode(altered(tmp_path,lambda d:d['variants'][0]['beats'][2].__setitem__('start',0)))

def test_no_unmeasured_voice():
 d=json.loads(MAN.with_name(json.loads(MAN.read_text())['plan_path']).read_text())
 for v in d['variants']:
  a=v['audio_qa'];assert a['status']=='PASS' and a['voice']=='en-US-AndrewNeural' and a['rate']=='+5%'
  assert sum(a['silence_gaps'])<=5 and max(a['silence_gaps'])<=.9
  assert -17.5<=a['loudness']['integrated_lufs']<=-14.5

def test_smooth_entry_warning_then_driver_response():
 assert m.lane_return_offset(1)>.3 and m.lane_return_offset(90)==0
 assert m.lane_return_offset(720)==0 and m.lane_return_offset(900)>.3
 assert m.rumble_displacement(1)==0
 assert len({m.travel_x(i) for i in range(1,901)})==900
 assert max(abs(m.lane_return_heading(i)) for i in range(1,901))<.4

def native_fixture(tmp_path):
 import importlib.util
 from shorts_studio.factory.curious_mechanics_native_qa import digest
 spec=importlib.util.spec_from_file_location('_native_fixtures',ROOT/'tests/test_factory_rumble_native_shard_qa.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
 p=fixtures.make(tmp_path);e=m.load_episode(MAN);shot=e['shots'][0]['id'];script=ROOT/'benchmarks/road_safety/render_curious_mechanics.py'
 p.update(episode_id=e['episode_id'],renderer_source_sha256=digest(script),camera_by_shot={shot:[[2,3,4],[0,0,0],15.5]})
 for r in p['original_frame_records']:r.update(shot_id=shot,absolute_x_m=round(m.travel_x(r['frame']),7),visible_car_screen_bounds=[.1,.3,.9,.7])
 for k,path in [('timeline_source_sha256',ROOT/'shorts_studio/factory/curious_mechanics_timeline.py'),('canonical_timeline_sha256',ROOT/'shorts_studio/factory/rumble_episode2.py'),('manifest_sha256',MAN),('experiment_plan_sha256',MAN.with_name(json.loads(MAN.read_text())['plan_path']))]:p[k]=digest(path)
 return p,script

@pytest.mark.parametrize('change',[None,'preview','binding','clipped','floating','repeated'])
def test_native_adapter_retains_real_frame_and_binding_gates(tmp_path,change):
 from shorts_studio.factory.curious_mechanics_native_qa import verify,digest
 p,script=native_fixture(tmp_path)
 if change=='preview':p['preview_only']=True
 if change=='binding':p['experiment_plan_sha256']='0'*64
 if change=='clipped':p['original_frame_records'][0]['visible_car_screen_bounds'][0]=-.1
 if change=='floating':p['original_frame_records'][0]['near_tyre_min_z_m']['Front_tire']=.1
 if change=='repeated':
  (tmp_path/'frame_0002.png').write_bytes((tmp_path/'frame_0001.png').read_bytes());p['original_frame_records'][1]['sha256']=digest(tmp_path/'frame_0002.png')
 (tmp_path/'episode-proof.json').write_text(json.dumps(p))
 if change:
  with pytest.raises(ValueError):verify(tmp_path,MAN,script)
 else:assert verify(tmp_path,MAN,script)['upload_authorized'] is False
