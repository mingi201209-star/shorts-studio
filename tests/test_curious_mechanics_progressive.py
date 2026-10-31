import pytest
from shorts_studio.factory.curious_mechanics_timeline import progressive_cuts


def test_progressive_roles_cover_film_without_returning_to_an_earlier_role():
    cuts = progressive_cuts([135, 310, 460, 767, 900])
    assert [role for _, role in cuts] == [
        'shoulder_location', 'road_cut', 'tire_contact',
        'rumble_mechanism', 'driver_response',
    ]
    assert len({role for _, role in cuts}) == len(cuts)


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
