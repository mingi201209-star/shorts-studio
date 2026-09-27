import hashlib
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from shorts_studio.models import Project, Scene, VisualBeat, VisualChange
from shorts_studio.visual_change import audit_visual_changes, equivalent_framing, resolve_visual_cues


def beat(tmp_path, i, kind='state', concept='wheel', state=None, content=None):
    p = tmp_path / f'{i}.png'
    p.write_bytes(content or str(i).encode())
    return VisualBeat(start=i*2, asset=str(p), visual_change=VisualChange(
        kind=kind, concept_id=concept, state_id=state or str(i),
        narration_cue=['기차는', '차축에', '반지름이'][i], added_information=f'fact {i}',
        source_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))


def project(beats):
    return Project(title='test', strict_meaningful_visual_changes=True, scenes=[Scene(
        id='one', narration='기차는 차축에 반지름이 있습니다.', visual_description='wheel', visual_beats=beats)])


def test_framing_cycle_is_never_three_meaningful_events(tmp_path):
    p=project([beat(tmp_path,0,'concept'),beat(tmp_path,1,'framing'),beat(tmp_path,2,'framing')])
    assert audit_visual_changes(p)['status']=='FAIL'


def test_new_state_and_new_concept_are_structurally_eligible(tmp_path):
    p=project([beat(tmp_path,0,'concept'),beat(tmp_path,1),beat(tmp_path,2,'concept','radius')])
    assert audit_visual_changes(p)['status']=='PASS'
    assert audit_visual_changes(p)['semantic_status']=='REQUIRES_VISUAL_REVIEW'


@pytest.mark.parametrize('attack',['same_hash','same_state','missing_cue','wrong_hash','fake_concept'])
def test_fabricated_metadata_does_not_pass(tmp_path,attack):
    a,b=beat(tmp_path,0,'concept'),beat(tmp_path,1)
    if attack=='same_hash':
        Path(b.asset).write_bytes(Path(a.asset).read_bytes());b.visual_change.source_sha256=a.visual_change.source_sha256
    elif attack=='same_state':b.visual_change.state_id=a.visual_change.state_id
    elif attack=='missing_cue':b.visual_change.narration_cue='absent'
    elif attack=='wrong_hash':b.visual_change.source_sha256='0'*64
    else:b.visual_change.kind='concept'
    assert audit_visual_changes(project([a,b]))['status']=='FAIL'


def test_real_tts_cues_replace_nominal_cut_times(tmp_path):
    p=project([beat(tmp_path,0,'concept'),beat(tmp_path,1)])
    resolved=resolve_visual_cues(p.scenes[0],[{'text':'기차는','start':.05},{'text':'차축에','start':2.37}],5)
    assert [b.start for b in resolved.visual_beats]==[0,2.37]
    assert p.scenes[0].visual_beats[1].start==2


def test_missing_measured_cue_fails_closed(tmp_path):
    p=project([beat(tmp_path,0,'concept'),beat(tmp_path,1)])
    with pytest.raises(ValueError):resolve_visual_cues(p.scenes[0],[{'text':'기차는','start':0}],5)


def _photo():
    rng=np.random.default_rng(29)
    a=np.full((480,480,3),245,np.uint8)
    for _ in range(80):
        xy=tuple(int(x) for x in rng.integers(30,450,2));color=tuple(int(x) for x in rng.integers(0,210,3))
        cv2.circle(a,xy,int(rng.integers(3,13)),color,-1)
    return a


def test_repeated_photo_crop_is_equivalent_even_when_renamed():
    a=_photo();b=cv2.resize(a[40:440,40:440],(480,480))
    assert equivalent_framing(a,b)


def test_diagram_reveal_is_not_equivalent_to_unchanged_diagram():
    a=_photo();b=a.copy()
    cv2.arrowedLine(b,(60,270),(400,270),(0,0,200),22)
    cv2.circle(b,(300,330),48,(0,180,50),-1)
    assert not equivalent_framing(a,b)


def test_identical_state_is_equivalent():
    a=_photo();assert equivalent_framing(a,a.copy())


def test_readable_hold_with_state_addition_keeps_legacy_cadence():
    from shorts_studio.final_video_qa import verify_visual_cut_cadence
    s=SimpleNamespace(id='s',visual_beats=[SimpleNamespace(start=0,asset='base'),SimpleNamespace(start=2.5,asset='arrow')])
    assert verify_visual_cut_cadence([{'scene':'s','duration':5}], [s])['status']=='PASS'


def _real_clip(tmp_path, images, seconds):
    """Encode an actual MP4 with the production media geometry; no mocked frames."""
    path=tmp_path/'states.mp4'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),12,(1080,1920))
    assert writer.isOpened()
    for image,duration in zip(images,seconds):
        frame=np.zeros((1920,1080,3),np.uint8)
        h,w=image.shape[:2];scale=min(980/w,950/h);sw,sh=round(w*scale),round(h*scale)
        ox,oy=(1080-sw)//2,280+(950-sh)//2
        frame[oy:oy+sh,ox:ox+sw]=cv2.resize(image,(sw,sh),interpolation=cv2.INTER_LANCZOS4)
        for _ in range(round(duration*12)):writer.write(frame)
    writer.release()
    return path


def _observed_fixture(tmp_path,images,seconds):
    from shorts_studio.visual_change import verify_observed_changes
    beats=[];cursor=0
    for i,a in enumerate(images):
        path=tmp_path/f'frame{i}.png';cv2.imwrite(str(path),a)
        beats.append(VisualBeat(start=cursor,asset=str(path),visual_change=VisualChange(
            kind='concept' if i==0 else 'state',concept_id='demo',state_id=str(i),
            narration_cue=f'cue{i}',added_information=f'detail{i}',source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())))
        cursor+=seconds[i]
    p=project(beats)
    video=_real_clip(tmp_path,images,seconds)
    return p,video,[{'scene':'one','start':0,'duration':cursor}],verify_observed_changes


def test_real_five_second_hold_with_narrated_arrow_addition_passes(tmp_path):
    a=_photo();b=a.copy();cv2.arrowedLine(b,(70,280),(410,280),(0,0,220),25)
    p,v,w,verify=_observed_fixture(tmp_path,[a,b],[2.5,2.5])
    result=verify(p,w,v,tmp_path,(280,1230))
    assert result['status']=='PASS',result
    assert result['first_5s_meaningful_changes']==1


def test_real_one_second_equivalent_crops_fail_as_churn(tmp_path):
    a=_photo();b=cv2.resize(a[30:450,30:450],(480,480));c=cv2.resize(a[45:435,45:435],(480,480))
    p,v,w,verify=_observed_fixture(tmp_path,[a,b,c],[1,1,1])
    result=verify(p,w,v,tmp_path,(280,1230))
    assert result['status']=='FAIL'
    assert any('equivalent crop' in f for f in result['failures'])


def test_wrong_changing_frames_cannot_replace_declared_states(tmp_path):
    a=_photo();b=a.copy();cv2.rectangle(b,(120,200),(400,350),(0,150,0),-1)
    p,v,w,verify=_observed_fixture(tmp_path,[a,b],[2.5,2.5])
    cv2.imwrite(p.scenes[0].visual_beats[1].asset,np.zeros_like(b))
    result=verify(p,w,v,tmp_path,(280,1230))
    assert result['status']=='FAIL'
    assert any('pinned source' in f for f in result['failures'])


def test_simple_diagram_crop_does_not_gain_credit():
    a=np.full((480,480,3),245,np.uint8)
    cv2.line(a,(40,210),(440,210),(20,30,40),18)
    for x in [120,360]:cv2.circle(a,(x,220),70,(20,30,40),12)
    cv2.line(a,(30,295),(450,295),(100,100,100),10)
    b=cv2.resize(a[30:450,30:450],(480,480))
    assert equivalent_framing(a,b)


def test_semantic_provider_receives_actual_media_box_without_gutters(tmp_path):
    from PIL import Image
    from shorts_studio.visual_qa import evaluate_scene_semantics
    a=_photo();video=_real_clip(tmp_path,[a],[1])
    seen={}
    class Provider:
        def evaluate(self,image,requirements,**context):
            seen['size']=Image.open(image).size
            seen['labels']=context['positive_labels']
            return {'status':'NOT_EVALUATED','reason':'deliberately inconclusive'}
    scene=SimpleNamespace(id='s',visual_qa_requirements=['railway diagram'],visual_qa_labels=['wheelset'])
    result=evaluate_scene_semantics(scene,video,Provider(),tmp_path/'semantic.png',media_box=(280,1230))
    assert seen=={'size':(1080,950),'labels':['wheelset']}
    assert result['status']=='NOT_EVALUATED'  # cropping never promotes a verdict
