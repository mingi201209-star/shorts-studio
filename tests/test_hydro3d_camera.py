from shorts_studio import hydro3d


def test_hydro_camera_is_fixed_and_topic_optimized():
    camera = hydro3d.OPTIMAL_HYDRO_CAMERA
    assert -0.30 < camera.yaw < -0.10
    assert -0.32 < camera.pitch < -0.15
    assert 360.0 < camera.cx < 470.0
    assert 400.0 < camera.cy < 510.0

    for kind in hydro3d.KINDS:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            assert hydro3d.camera_for(kind, t) == camera


def test_hydro_hero_frame_is_nonblank():
    frame = hydro3d.render_hydro_frame("hero_contact", 1.0, width=980, height=950)
    extrema = frame.convert("RGB").getextrema()
    assert all(lo != hi for lo, hi in extrema)
