from shorts_studio import golf3d


def test_golf_video_uses_one_topic_optimized_camera():
    camera = golf3d.OPTIMAL_GOLF_CAMERA

    # Fixed slightly-above diagonal view: enough top surface to read the
    # dimples as 3D geometry while keeping the downstream wake legible.
    assert -0.42 < camera.yaw < -0.25
    assert -0.34 < camera.pitch < -0.18

    # Ball is intentionally left of center to reserve mobile-screen room for
    # the wake. This is topic-specific composition, not a global camera rule.
    assert camera.cx < 490
    assert camera.cy > 400

    for kind in golf3d.KINDS:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            assert golf3d.camera_for(kind, t) == camera


def test_golf_hero_frame_is_not_blank():
    frame = golf3d.render_golf_frame("hero_dimples", 0.5)
    assert frame.size == (980, 950)
    bbox = frame.convert("RGB").getbbox()
    assert bbox is not None
