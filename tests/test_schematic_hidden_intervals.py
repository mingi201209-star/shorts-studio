from benchmarks.road_safety.curious_mechanics_fast_batch import schematic


def _seconds(stamp):
    hours, minutes, seconds = stamp.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def test_schematic_is_absent_during_human_action(tmp_path):
    episode = {
        "shots": [
            {
                "id": "B_00_driver_response",
                "start": 1,
                "end": 900,
            }
        ]
    }

    path = schematic(
        "B",
        tmp_path,
        source_episode=episode,
        hidden_intervals=[(1.0, 2.0)],
    )

    events = [line for line in path.read_text().splitlines() if line.startswith("Dialogue:")]
    assert events
    intervals = [
        (_seconds(parts[1]), _seconds(parts[2]))
        for line in events
        if len(parts := line.split(",", 9)) == 10
    ]
    assert any(start < 1.0 for start, _ in intervals)
    assert any(end > 2.0 for _, end in intervals)
    assert all(end <= 1.0 or start >= 2.0 for start, end in intervals)
