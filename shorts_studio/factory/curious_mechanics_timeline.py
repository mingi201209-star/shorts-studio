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
_PROGRESSIVE=set()
PROGRESSIVE_STYLES=('shoulder_location','road_cut','tire_contact','rumble_mechanism','driver_response')

def _normalize_progressive_roles(roles):
    """Each entry is either a canonical base-style name (role == base), or a
    [role_name, base_style] pair giving one shot a distinct, descriptive role
    while its camera/semantic/detail lookups still resolve to a real,
    already-defined base style in original.SHOT_IDS. This lets one base style
    (e.g. 'rumble_mechanism') carry two visually distinct sub-beats without
    ever inventing a camera the canonical module doesn't already know."""
    normalized = [tuple(r) if isinstance(r, (list, tuple)) else (r, r) for r in roles]
    if any(base not in original.SHOT_IDS for _, base in normalized):
        raise ValueError('progressive role maps to an unknown base style')
    return normalized

def expected_frame_count(seconds, fps=30):
    """Validate an opt-in duration without changing legacy 30s episodes."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('invalid episode duration')
    if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
        raise ValueError('invalid fps')
    frames = seconds * fps
    if not math.isclose(frames, round(frames), abs_tol=1e-7):
        raise ValueError('duration does not align to a whole frame')
    return int(round(frames))


def progressive_cuts(ends, roles=PROGRESSIVE_STYLES, *, total_frames=900):
    normalized = _normalize_progressive_roles(roles)
    if (not isinstance(ends,list) or len(ends)!=len(normalized)
            or any(type(n) is not int for n in ends)
            or ends[-1]!=total_frames or ends[0]<30
            or any(b-a<30 for a,b in zip(ends,ends[1:]))):
        raise ValueError('invalid progressive native shot coverage')
    return list(zip(ends,roles))
ROAD_X_HALF_SPAN=32.0
ROAD_Y_NEAR_EDGE=-40.0
DIRT_Y_FAR_EDGE=40.0
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
    shots=[];start=1;_STYLE.clear();_PROGRESSIVE.clear()
    cuts=[]
    for index,(beat,styles) in enumerate(zip(beats,STYLES[ident])):
        first=round(beat['start']*30)+1;last=round(beat['end']*30)
        if len(styles)==1: cuts.append((last,styles[0]));continue
        if ident=='A' and index==1: middle=first+29
        else: middle=(first+last)//2
        cuts.extend([(middle,styles[0]),(last,styles[1])])
    if 'progressive_cut_frames' in data:
        roles = data.get('progressive_styles', PROGRESSIVE_STYLES)
        cuts=progressive_cuts(data['progressive_cut_frames'], roles)
        if not isinstance(data.get('measured_audio_sha256'),str) or len(data['measured_audio_sha256'])!=64:
            raise ValueError('progressive audio binding missing')
    for i,(end,style) in enumerate(cuts):
        role,base=tuple(style) if isinstance(style,(list,tuple)) else (style,style)
        name=f'{ident}_{i:02}_{role}';_STYLE[name]=base
        if 'progressive_cut_frames' in data: _PROGRESSIVE.add(name)
        shots.append(dict(id=name,start=start,end=end));start=end+1
    assert start==901 and all(s['end']>=s['start'] for s in shots)
    return dict(episode_id='curious-mechanics-'+ident,resolution=[1080,1920],cycles_samples=32,total_frames=900,fps=30,shots=shots)
def camera_layout(shot):
    layout=original.camera_layout(dict(shot,id=_STYLE[shot['id']]))
    if _STYLE[shot['id']] in ('shoulder_location','driver_response'): layout['scale']=15.5
    # travel_x moves ~2.8x faster over frames 1-90 than the rest of the film
    # (see travel_x below); a progressive-length 'hook_warning' opening covers
    # more absolute distance per frame than its native 5s-shot scale was fit
    # for, so it needs a wider fixed frame to keep the wheel from clipping out.
    if shot['id'] in _PROGRESSIVE and _STYLE[shot['id']]=='hook_warning': layout['scale']=3.2
    # A long wide-location shot needs a wider fixed frame to retain the actual
    # moving wheel throughout; never track the camera or reframe on shard
    # boundaries. The 'rumble_mechanism_close' sub-beat deliberately keeps the
    # unwidened native scale so the already-simulated body vibration reads --
    # which is also why its manifest boundary must end at/before frame 719:
    # lane_return_offset's lateral drift back toward the lane starts exactly
    # at frame 720, and this tight camera's frustum was never fit to also
    # absorb that second axis of motion on top of ongoing forward travel.
    if (shot['id'] in _PROGRESSIVE and _STYLE[shot['id']]=='rumble_mechanism'
            and not shot['id'].endswith('rumble_mechanism_close')):
        layout['scale']=7.6
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

