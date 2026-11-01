import pytest
from shorts_studio.factory.curious_mechanics_timeline import load_episode, progressive_cuts


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


def test_curious_mechanics_b_manifest_resolves_seven_distinct_roles_to_real_base_styles():
    episode = load_episode('examples/experiments/curious-mechanics-progressive-B.json')
    roles = ['_'.join(s['id'].split('_')[2:]) for s in episode['shots']]
    assert roles == [
        'hook_warning', 'shoulder_location', 'road_cut', 'tire_contact',
        'rumble_mechanism_wide', 'rumble_mechanism_close', 'driver_response',
    ]
    assert len(roles) == len(set(roles))
    assert [s['start'] for s in episode['shots']] == [1, 51, 136, 311, 461, 607, 720]
    assert [s['end'] for s in episode['shots']] == [50, 135, 310, 460, 606, 719, 900]


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
