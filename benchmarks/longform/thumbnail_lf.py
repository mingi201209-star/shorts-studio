"""Long-form thumbnails (1280x720 JPEG) from 16:9 stills rendered by storyboard_lf.py: a light grade for small screens (a little more
contrast and colour, a soft vignette) and, where asked, a short headline in heavy type with a dark outline. Text lives only on the
thumbnail, never in the video (no-scene-text rule).

usage: python3 benchmarks/longform/thumbnail_lf.py STILL.png OUT.jpg [--text "ROADS|FIGHT BACK"] [--corner tl|tr|bl|br]
A '|' in the text breaks the line; the last line is drawn in the accent colour."""
from __future__ import annotations

import argparse

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

SIZE = (1280, 720)
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
WHITE, ACCENT, INK = (255, 255, 255), (255, 214, 0), (10, 10, 10)


def grade(im: Image.Image) -> Image.Image:
    im = im.convert("RGB").resize(SIZE, Image.LANCZOS)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    im = ImageEnhance.Color(im).enhance(1.18)
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((-0.15 * w, -0.25 * h, 1.15 * w, 1.25 * h), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(90))
    dark = ImageEnhance.Brightness(im).enhance(0.72)
    return Image.composite(im, dark, mask)


def headline(im: Image.Image, text: str, corner: str = "tl", height_px: int = 118) -> Image.Image:
    lines = text.split("|")
    font = ImageFont.truetype(FONT, height_px)
    d = ImageDraw.Draw(im)
    stroke = max(6, height_px // 11)
    gap = int(height_px * 0.12)
    boxes = [d.textbbox((0, 0), ln, font=font, stroke_width=stroke) for ln in lines]
    widths = [b[2] - b[0] for b in boxes]
    heights = [b[3] - b[1] for b in boxes]
    block_h = sum(heights) + gap * (len(lines) - 1)
    margin = 38
    y = margin if corner[0] == "t" else SIZE[1] - margin - block_h
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    pos = []
    for i, ln in enumerate(lines):
        x = margin if corner[1] == "l" else SIZE[0] - margin - widths[i]
        pos.append((x - boxes[i][0], y - boxes[i][1]))
        sd.text((pos[-1][0] + 8, pos[-1][1] + 10), ln, font=font, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
        y += heights[i] + gap
    im = Image.alpha_composite(im.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(9))).convert("RGB")
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        d.text(pos[i], ln, font=font, fill=ACCENT if i == len(lines) - 1 and len(lines) > 1 else WHITE, stroke_width=stroke, stroke_fill=INK)
    return im


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("still")
    ap.add_argument("out")
    ap.add_argument("--text", default="")
    ap.add_argument("--corner", default="tl")
    ap.add_argument("--size", type=int, default=118)
    a = ap.parse_args()
    im = grade(Image.open(a.still))
    if a.text:
        im = headline(im, a.text, a.corner, a.size)
    im.save(a.out, quality=92, optimize=True, progressive=True)
    print(a.out, im.size)


if __name__ == "__main__":
    main()
