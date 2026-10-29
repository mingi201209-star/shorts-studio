"""Opt-in viewer-first experiment; canonical episode gates remain unchanged."""
import importlib.util,json,math,sys,hashlib
from pathlib import Path
_spec=importlib.util.spec_from_file_location("canonical_rumble",Path(__file__).with_name("rumble_episode2.py"))
original=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(original)
for _name in dir(original):
    if not _name.startswith('_'): globals()[_name]=getattr(original,_name)
# This module is loaded in a new Blender process per variant.
_STYLE={}
ROAD_X_HALF_SPAN=22.0
ROAD_Y_NEAR_EDGE=-20.0
DIRT_Y_FAR_EDGE=22.0
STYLES={
 'A':[['shoulder_location'],['tire_contact','road_cut'],['road_cut','shoulder_location'],['tire_contact','rumble_mechanism'],['shoulder_location','rumble_mechanism'],['driver_response']],
 'B':[['shoulder_location','tire_contact'],['road_cut','shoulder_location'],['tire_contact','rumble_mechanism'],['shoulder_location','tire_contact'],['shoulder_location','rumble_mechanism'],['driver_response']],
 'C':[['shoulder_location','tire_contact'],['shoulder_location','road_cut'],['tire_contact','rumble_mechanism'],['rumble_mechanism','shoulder_location'],['shoulder_location','rumble_mechanism'],['driver_response']],
}
def load_episode(path):
    data=json.loads(Path(path).read_text()); ident=data['variant_id']
    if ident not in STYLES: raise ValueError('unknown variant')
    if Path(data['plan_path']).name!=data['plan_path']: raise ValueError('plan must be a sibling file')
    raw=Path(path).with_name(data['plan_path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=data['plan_sha256']: raise ValueError('plan binding mismatch')
    plan=json.loads(raw)
    c=plan['controls'];s=plan['safety']
    if (c['target_seconds'],c['fps'],c['resolution'],c['samples'])!=(30,30,[1080,1920],32): raise ValueError('production quality changed')
    if any(s[k] for k in ('upload_authorized','auto_upload','paid_api','merge_authorized','quality_thresholds_changed','frame_holds_or_interpolation')): raise ValueError('unsafe experiment configuration')
    variant=next(v for v in plan['variants'] if v['id']==ident)
    beats=variant['beats']
    if len(beats)!=6 or beats[0]['start']!=0 or abs(beats[-1]['end']-30)>.001: raise ValueError('incomplete narration schedule')
    if any(a['end']!=b['start'] for a,b in zip(beats,beats[1:])) or any(b['end']<=b['start'] for b in beats): raise ValueError('overlapping/gapped beats')
    if variant['audio_qa']['status']!='PASS': raise ValueError('measured audio QA missing')
    shots=[];start=1;_STYLE.clear()
    cuts=[]
    for index,(beat,styles) in enumerate(zip(beats,STYLES[ident])):
        first=round(beat['start']*30)+1;last=round(beat['end']*30)
        if len(styles)==1: cuts.append((last,styles[0]));continue
        if ident=='A' and index==1: middle=first+29
        else: middle=(first+last)//2
        cuts.extend([(middle,styles[0]),(last,styles[1])])
    for i,(end,style) in enumerate(cuts):
        name=f'{ident}_{i:02}_{style}';_STYLE[name]=style
        shots.append(dict(id=name,start=start,end=end));start=end+1
    assert start==901 and all(s['end']>=s['start'] for s in shots)
    return dict(episode_id='curious-mechanics-'+ident,resolution=[1080,1920],cycles_samples=32,total_frames=900,fps=30,shots=shots)
def camera_layout(shot):
    layout=original.camera_layout(dict(shot,id=_STYLE[shot['id']]))
    if _STYLE[shot['id']] in ('shoulder_location','driver_response'): layout['scale']=15.5
    return layout
def detail_stage(ident): return original.detail_stage(_STYLE[ident])
def detail_visibility(ident): return original.detail_visibility(_STYLE[ident])
def _smooth(t):
    t=max(0.,min(1.,t));return t*t*(3-2*t)
def travel_x(frame):
    original.travel_x(frame)
    return -4.2+2*(frame-1)/89 if frame<=90 else -2.2+6.4*(frame-90)/810
def lane_return_offset(frame):
    original.travel_x(frame)
    return .36*(1-_smooth((frame-1)/74))+.36*_smooth((frame-720)/180)
def lane_return_heading(frame):
    lo=max(1,frame-1);hi=min(900,frame+1)
    return math.atan2(lane_return_offset(hi)-lane_return_offset(lo),travel_x(hi)-travel_x(lo))
def rumble_displacement(frame):
    # Explanatory kinematics, suppressed while the wheel is in the smooth lane.
    overlap=max(0.,min(1.,(.30-lane_return_offset(frame))/.20))
    return overlap*.008*math.sin(travel_x(frame)/.34*math.tau)
