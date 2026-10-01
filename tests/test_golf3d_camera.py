from shorts_studio import golf3d


def test_golf_video_uses_one_topic_optimized_camera():
    camera = golf3d.OPTIMAL_GOLF_CAMERA

    # Shallow 3/4 viewpoint: enough surface depth to read dimples, but still
    # near side-on so the downstream wake remains legible.
    assert -0.35 < camera.yaw < -0.15
    assert -0.18 < camera.pitch < -0.05

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
