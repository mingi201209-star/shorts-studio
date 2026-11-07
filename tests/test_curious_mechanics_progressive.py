import pytest

from benchmarks.road_safety.curious_mechanics_select_preview_frames import (
    critical_preview_frames,
)
from shorts_studio.factory.curious_mechanics_timeline import (
    camera_layout,
    load_episode,
    progressive_cuts,
    rumble_displacement,
)


def test_progressive_roles_cover_film_without_returning_to_an_earlier_role():
    cuts = progressive_cuts([135, 310, 460, 767, 900])
    assert [role for _, role in cuts] == [
        'shoulder_location', 'road_cut', 'tire_contact',
        'rumble_mechanism', 'driver_response',
    ]
    assert len({role for _, role in cuts}) == len(cuts)


def test_progressive_cuts_accepts_a_distinct_role_mapped_to_a_shared_base_style():
    # A [role, base] pair lets two differently-framed sub-beats (e.g. a wide
    # location shot and a close vibration shot) reuse the same already-defined
    # canonical camera/semantic/detail-stage contract ('rumble_mechanism')
    # without colliding on role uniqueness.
    cuts = progressive_cuts(
        [75, 135, 310, 460, 606, 767, 900],
        roles=[
            'hook_warning', 'shoulder_location', 'road_cut', 'tire_contact',
            ['rumble_mechanism_wide', 'rumble_mechanism'],
            ['rumble_mechanism_close', 'rumble_mechanism'],
            'driver_response',
        ],
    )
    roles = [role for _, role in cuts]
    assert roles[4] == ['rumble_mechanism_wide', 'rumble_mechanism']
    assert roles[5] == ['rumble_mechanism_close', 'rumble_mechanism']


def test_progressive_cuts_rejects_a_role_mapped_to_an_unknown_base_style():
    with pytest.raises(ValueError):
        progressive_cuts([900], roles=[['invented_role', 'not_a_real_style']])


def test_curious_mechanics_b_manifest_resolves_nine_distinct_roles_to_real_base_styles():
    # 'rumble_mechanism_return' (720-767) exists because driver_response must
    # stay at its proven-safe 768-900/4.43s span -- extending it back to 720
    # once failed final_video_qa's visual_activity check (a real 6.0s static
    # window, >5.0s threshold: the wide, slow driver_response camera doesn't
    # register enough real pixel change over a full 6s). The freed 720-767
    # frames get their own short bridging shot instead, reusing the same
    # wide scale (7.6) the original single 461-767 shot proved safe there.
    episode = load_episode('examples/experiments/curious-mechanics-progressive-B.json')
    roles = ['_'.join(s['id'].split('_')[2:]) for s in episode['shots']]
    assert roles == [
        'hook_warning', 'shoulder_location', 'road_cut_top', 'road_cut_side',
        'tire_contact',
        'rumble_mechanism_wide', 'rumble_mechanism_close',
        'rumble_mechanism_return', 'driver_response',
    ]
    assert len(roles) == len(set(roles))
    assert [s['start'] for s in episode['shots']] == [1, 51, 136, 219, 311, 461, 607, 720, 768]
    assert [s['end'] for s in episode['shots']] == [50, 135, 218, 310, 460, 606, 719, 767, 900]


def test_progressive_rumble_motion_is_visible_but_stays_bounded():
    amplitudes = [abs(rumble_displacement(frame)) for frame in range(461, 720)]
    assert max(amplitudes) > .02
    assert max(amplitudes) < .03



def test_close_vibration_beat_frames_real_tyre_and_wheel_arch_without_changing_motion():
    episode = load_episode('examples/experiments/curious-mechanics-progressive-B.json')
    close = next(s for s in episode['shots'] if s['id'].endswith('rumble_mechanism_close'))
    layout = camera_layout(close)

    assert (close['start'], close['end']) == (607, 719)
    assert layout['target'] == 'wheel'
    assert layout['anchor_frame'] == 663
    assert layout['scale'] == 3.15
    assert layout['target_z'] == .12
    assert max(abs(rumble_displacement(f)) for f in range(607, 720)) < .03


def test_curious_mechanics_a_and_c_manifests_are_unaffected_by_the_b_extension():
    for variant, path in (
        ('A', 'examples/experiments/curious-mechanics-progressive-A.json'),
        ('C', 'examples/experiments/curious-mechanics-progressive-C.json'),
    ):
        episode = load_episode(path)
        roles = ['_'.join(s['id'].split('_')[2:]) for s in episode['shots']]
        assert roles == [
            'shoulder_location', 'road_cut', 'tire_contact',
            'rumble_mechanism', 'driver_response',
        ]


def test_critical_preview_frames_would_have_flagged_both_real_clipping_failures():
    # Regression guard for two real CI failures hit while developing the
    # causal-shot structure: frame 74 clipped inside an (since-fixed) 1-75
    # hook_warning span, and frame 754 clipped inside an (since-fixed) 607-767
    # rumble_mechanism_close span that ran into lane_return_offset's drift
    # starting at frame 720. Both spans' own end frame -- which this function
    # always includes, since travel_x is monotonic -- is at least as clipped
    # as the real failure frame found inside them, so a --preview check of
    # the selected frames would have caught both before the real 32-sample
    # production matrix ran.
    buggy_hook_warning_episode = dict(shots=[
        dict(id='B_00_hook_warning', start=1, end=75),
        dict(id='B_01_shoulder_location', start=76, end=900),
    ])
    frames = critical_preview_frames(buggy_hook_warning_episode)
    assert 75 in frames

    buggy_rumble_close_episode = dict(shots=[
        dict(id='B_00_x', start=1, end=606),
        dict(id='B_01_rumble_mechanism_close', start=607, end=767),
        dict(id='B_02_driver_response', start=768, end=900),
    ])
    frames = critical_preview_frames(buggy_rumble_close_episode)
    assert 767 in frames
    assert 720 in frames  # the actual root-cause breakpoint, not just the end


def test_critical_preview_frames_chunk_fits_the_preview_tool_sparse_limit():
    episode = load_episode('examples/experiments/curious-mechanics-progressive-B.json')
    frames = critical_preview_frames(episode)
    assert frames == sorted(set(frames))  # sorted, deduplicated
    assert 616 in frames
    assert 637 in frames
    # render_curious_mechanics.py caps --preview --frame-list at 12 frames;
    # confirm the real B manifest needs (and this test documents) 3 chunks.
    chunk_size = 12
    chunks = [frames[i:i + chunk_size] for i in range(0, len(frames), chunk_size)]
    assert all(len(c) <= chunk_size for c in chunks)
    assert len(chunks) == 3


@pytest.mark.parametrize('ends', [
    [135, 310, 460, 767, 899],
    [135, 310, 309, 767, 900],
    [True, 310, 460, 767, 900],
    [135, 310, 460, 767],
    [135, 310, 460, 890, 900],
])
def test_progressive_plan_rejects_missing_overlapping_or_short_shots(ends):
    with pytest.raises(ValueError):
        progressive_cuts(ends)
