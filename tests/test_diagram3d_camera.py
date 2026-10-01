from shorts_studio import diagram3d


def test_every_3d_beat_uses_one_front_camera():
    expected = diagram3d._FRONT_CAMERA
    assert expected.yaw == 0.0
    assert expected.pitch == -0.18

    for kind in diagram3d._FRONT_CAMERA_KINDS:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            assert diagram3d._camera_for(kind, t) == expected
