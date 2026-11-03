import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from benchmarks.road_safety.curious_mechanics_delivery import validate_layout,LEGACY,semantic_evidence
from shorts_studio.factory import curious_mechanics_timeline as timeline

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


def _semantic_style(shot_id):
    # Mirrors curious_mechanics_delivery.semantic()'s style-resolution line.
    return timeline._STYLE.get(shot_id) or '_'.join(shot_id.split('_')[2:])


def test_semantic_style_resolves_progressive_sub_beats_to_their_shared_base():
    # Regression guard: run 41274189435's final job crashed with
    # KeyError('rumble_mechanism_wide') because semantic() used to derive the
    # canonical reference/label style by blindly stripping the id prefix,
    # which only works when role == base style. B's split rumble_mechanism
    # sub-beats (_wide/_close/_return) need to resolve to the shared base
    # 'rumble_mechanism' instead, the same way camera/detail lookups already
    # do via curious_mechanics_timeline._STYLE.
    episode = timeline.load_episode('examples/experiments/curious-mechanics-progressive-B.json')
    base = timeline.original.load_episode(Path('examples/factory/rumble-episode2-30s.json'))
    by_id = {s['id']: s for s in base['shots']}
    for shot in episode['shots']:
        style = _semantic_style(shot['id'])
        assert style in by_id, (shot['id'], style)
        timeline.original.semantic_labels(style)  # must not raise


def test_semantic_style_fallback_matches_old_behavior_for_unsplit_roles():
    # A caller that builds its own episode dict without calling
    # load_episode() first (curious_mechanics_fast_batch.py) never populates
    # _STYLE; for those (role == base already) the fallback plain id-suffix
    # derivation must still give the same answer it always did.
    timeline._STYLE.clear()
    assert _semantic_style('A_00_hook_warning') == 'hook_warning'
    assert _semantic_style('B_03_driver_response') == 'driver_response'

def test_top_and_side_road_cut_use_truthful_distinct_semantic_evidence():
    base = timeline.original.load_episode(Path('examples/factory/rumble-episode2-30s.json'))
    reference = next(shot for shot in base['shots'] if shot['id'] == 'road_cut')
    top_requirements, top_labels = semantic_evidence(
        'B_02_road_cut_top', 'road_cut', reference)
    side_requirements, side_labels = semantic_evidence(
        'B_03_road_cut_side', 'road_cut', reference)

    assert any('overhead' in label or 'top down' in label for label in top_labels)
    assert all('cross section' not in label for label in top_labels)
    assert top_requirements != side_requirements
    assert top_labels != side_labels
    assert side_requirements == reference['visual_proof']
    assert side_labels == list(timeline.original.semantic_labels('road_cut'))
