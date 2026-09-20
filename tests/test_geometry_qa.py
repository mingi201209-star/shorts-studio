"""Real (non-ML) corner-geometry and image-clarity vision checks.

These exercise actual OpenCV contour/curvature measurements against
synthetically drawn shapes, so they run fully offline and deterministically.
"""
from PIL import Image, ImageDraw
from shorts_studio.visual_qa import (
    CornerGeometryVisionProvider, ClarityVisionProvider, CompositeVisionProvider,
)

def _square_frame(path):
    img = Image.new("RGB", (600, 400), (30, 30, 30))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 260, 340], fill=(230, 230, 230))
    img.save(path)

def _rounded_frame(path):
    img = Image.new("RGB", (600, 400), (30, 30, 30))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 60, 260, 340], radius=80, fill=(230, 230, 230))
    img.save(path)

def _compare_frame(path):
    img = Image.new("RGB", (900, 400), (30, 30, 30))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 340, 340], fill=(230, 230, 230))
    d.rounded_rectangle([560, 60, 840, 340], radius=90, fill=(230, 230, 230))
    img.save(path)

def _blank_frame(path):
    Image.new("RGB", (600, 400), (128, 128, 128)).save(path)

def test_square_corners_detected_as_square(tmp_path):
    p = tmp_path / "sq.jpg"; _square_frame(p)
    q = CornerGeometryVisionProvider().evaluate(p, ["왼쪽은 네 개의 90도 모서리"])
    assert q["status"] == "PASS"

def test_rounded_corners_detected_as_rounded(tmp_path):
    p = tmp_path / "rd.jpg"; _rounded_frame(p)
    q = CornerGeometryVisionProvider().evaluate(p, ["현대식 둥근 모서리가 명확히 보여야 함"])
    assert q["status"] == "PASS"

def test_square_requirement_fails_on_rounded_frame(tmp_path):
    p = tmp_path / "rd2.jpg"; _rounded_frame(p)
    q = CornerGeometryVisionProvider().evaluate(p, ["네 개의 90도 모서리가 있어야 함"])
    assert q["status"] == "FAIL"

def test_round_requirement_fails_on_square_frame(tmp_path):
    p = tmp_path / "sq2.jpg"; _square_frame(p)
    q = CornerGeometryVisionProvider().evaluate(p, ["크게 둥근 모서리가 있어야 함"])
    assert q["status"] == "FAIL"

def test_side_by_side_square_and_round_are_distinguished(tmp_path):
    p = tmp_path / "cmp.jpg"; _compare_frame(p)
    q = CornerGeometryVisionProvider().evaluate(
        p, ["왼쪽은 네 개의 90도 모서리", "오른쪽은 크게 둥근 모서리", "두 형태가 즉시 구별되어야 함"]
    )
    assert q["status"] == "PASS"
    assert set(q["shapes"]) == {"square", "rounded"}

def test_side_by_side_requirement_fails_when_both_shapes_identical(tmp_path):
    img = Image.new("RGB", (900, 400), (30, 30, 30))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 340, 340], fill=(230, 230, 230))
    d.rectangle([560, 60, 840, 340], fill=(230, 230, 230))
    p = tmp_path / "same.jpg"; img.save(p)
    q = CornerGeometryVisionProvider().evaluate(
        p, ["왼쪽은 네 개의 90도 모서리", "오른쪽은 크게 둥근 모서리", "두 형태가 즉시 구별되어야 함"]
    )
    assert q["status"] == "FAIL"

def test_geometry_provider_not_applicable_without_corner_requirement(tmp_path):
    p = tmp_path / "sq3.jpg"; _square_frame(p)
    q = CornerGeometryVisionProvider().evaluate(p, ["subject must be clearly visible"])
    assert q["status"] == "NOT_EVALUATED"

def test_geometry_provider_defers_on_busy_real_photo_instead_of_false_fail(tmp_path):
    # A frame with no clean diagram-scale contour (small scattered shapes) must not
    # be forced into a confident PASS/FAIL -- it should hand off (NOT_EVALUATED).
    img = Image.new("RGB", (900, 1600), (40, 45, 60))
    d = ImageDraw.Draw(img)
    for i in range(20):
        d.ellipse([10 + i * 40, 10 + (i % 5) * 15, 30 + i * 40, 30 + (i % 5) * 15], fill=(200, 200, 200))
    p = tmp_path / "busy.jpg"; img.save(p)
    q = CornerGeometryVisionProvider().evaluate(p, ["현대식 둥근 모서리가 명확히 보여야 함"])
    assert q["status"] == "NOT_EVALUATED"

def test_clarity_provider_passes_normal_frame(tmp_path):
    p = tmp_path / "ok.jpg"; _compare_frame(p)
    q = ClarityVisionProvider().evaluate(p, ["anything"])
    assert q["status"] == "PASS"

def test_clarity_provider_fails_blank_frame(tmp_path):
    p = tmp_path / "blank.jpg"; _blank_frame(p)
    q = ClarityVisionProvider().evaluate(p, ["anything"])
    assert q["status"] == "FAIL"

def test_clarity_provider_not_evaluated_on_unreadable_frame(tmp_path):
    p = tmp_path / "missing.jpg"
    q = ClarityVisionProvider().evaluate(p, ["anything"])
    assert q["status"] == "NOT_EVALUATED"

def test_composite_provider_never_passes_when_everything_abstains(tmp_path):
    class Abstain:
        def evaluate(self, image, requirements, **context):
            return {"status": "NOT_EVALUATED", "reason": "no evidence"}
    p = tmp_path / "x.jpg"; _blank_frame(p)
    q = CompositeVisionProvider([Abstain(), Abstain()]).evaluate(p, ["subject visible"])
    assert q["status"] == "NOT_EVALUATED"

def test_composite_provider_fails_closed_on_malformed_sub_result(tmp_path):
    class Malformed:
        def evaluate(self, image, requirements, **context):
            return {"status": "MAYBE"}  # not a recognized status -- must never be treated as PASS
    class AlsoAbstain:
        def evaluate(self, image, requirements, **context):
            return {"status": "NOT_EVALUATED"}
    p = tmp_path / "y.jpg"; _blank_frame(p)
    q = CompositeVisionProvider([Malformed(), AlsoAbstain()]).evaluate(p, ["subject visible"])
    assert q["status"] != "PASS"
