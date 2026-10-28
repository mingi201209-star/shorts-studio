import pytest
from PIL import Image, ImageDraw

from shorts_studio.dual_mode_pipeline import marker_centroid, visible_motion_difference


def orange_frame(root, x, y):
    root.mkdir()
    image = Image.new("RGB", (100, 100), "black")
    ImageDraw.Draw(image).rectangle((x, y, x + 20, y + 20), fill=(255, 80, 0))
    image.save(root / "frame_0008.png")


def test_visible_marker_checks_rendered_pixels(tmp_path):
    a, b = tmp_path / "rolling", tmp_path / "locked"
    orange_frame(a, 10, 10)
    orange_frame(b, 50, 30)
    result = visible_motion_difference(a, b, 8)
    assert result["tracer_displacement_pixels"] > 40
    assert result["rolling_orange_pixels"] > 20


def test_identical_pixels_do_not_count_as_new_motion(tmp_path):
    a, b = tmp_path / "rolling", tmp_path / "locked"
    orange_frame(a, 10, 10)
    orange_frame(b, 10, 10)
    with pytest.raises(ValueError, match="indistinguishable"):
        visible_motion_difference(a, b, 8)


def test_invisible_marker_is_not_faked(tmp_path):
    path = tmp_path / "black.png"
    Image.new("RGB", (100, 100), "black").save(path)
    with pytest.raises(ValueError, match="not visible"):
        marker_centroid(path)
