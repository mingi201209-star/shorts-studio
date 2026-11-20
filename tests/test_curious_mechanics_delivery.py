import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from benchmarks.road_safety.curious_mechanics_delivery import validate_layout,LEGACY

def spans():
    rows=[]
    for start in range(1,901,30):
        nums=list(range(start,start+30))
        rows.append(dict(proof=dict(episode_id='curious-mechanics-A',first_frame=start,last_frame=start+29,frames=30,frame_numbers=nums,original_frame_records=[dict(frame=n) for n in nums],renderer_source_sha256=LEGACY,renderer='CYCLES',cycles_samples=32,resolution=[1080,1920],fps=30,preview_only=False,car_mesh_parts=72,rotating_wheel_pivots=4,physically_calibrated=False,upload_ready=False,camera_by_shot={'A_00':[[1,2,3],[0,0,0],15.5]}),rgb_md5=[str(n) for n in nums],controller_qa=dict(status='PASS_NATIVE_ORIGINAL_SHARD',frames=30)))
    return rows

@pytest.mark.parametrize('fault',[None,'gap','overlap','camera','clone','renderer','quality'])
def test_complete_source_bound_unique_native_contract(fault):
    rows=spans();canonical=copy.deepcopy(rows[0]['proof']['camera_by_shot'])
    if fault=='gap':rows.pop(4)
    if fault=='overlap':rows.insert(4,copy.deepcopy(rows[3]))
    if fault=='camera':rows[4]['proof']['camera_by_shot']['A_00'][0][0]+=.000001
    if fault=='clone':rows[4]['rgb_md5'][0]=rows[3]['rgb_md5'][0]
    if fault=='renderer':rows[4]['proof']['renderer_source_sha256']='0'*64
    if fault=='quality':rows[4]['proof']['cycles_samples']=7
    if fault:
        with pytest.raises(AssertionError):validate_layout(rows,canonical,'A')
    else:assert len(validate_layout(rows,canonical,'A'))==30


def test_source_substitution_requires_explicit_absolute_frame_mapping():
    rows=spans();canonical=copy.deepcopy(rows[0]['proof']['camera_by_shot']);rows[19]['proof']['episode_id']='curious-mechanics-B'
    with pytest.raises(AssertionError):validate_layout(rows,canonical,'A')
    assert len(validate_layout(rows,canonical,'A',{571:'B'}))==30
    with pytest.raises(AssertionError):validate_layout(rows,canonical,'A',{541:'B'})
