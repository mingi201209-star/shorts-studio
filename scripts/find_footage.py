#!/usr/bin/env python3
"""Find pinned, explicitly licensed footage and photos for a topic spec.

    python scripts/find_footage.py commons "soap bubble" --kind video --label "a real close-up of a soap bubble"
    python scripts/find_footage.py pexels 3999392 13891268 --label "real footage of a car on a wet road"
    python scripts/find_footage.py preview <url-or-file> --out build/preview.jpg

``commons`` searches Wikimedia Commons through its public API and keeps only files whose
machine-readable licence is free to reuse (public domain, CC0, CC BY, CC BY-SA). ``pexels``
resolves Pexels video ids (found on pexels.com, which has no keyless search API) to the
concrete MP4 the site serves, so the spec can pin a file instead of a page.

``preview`` downloads a video once into the shared cache (the production reuses that file)
and writes one contact sheet of evenly spaced frames with their times, so a trim point and
a crop can be chosen without scrubbing the file by hand.

With ``--label`` each candidate's preview frame is scored by the renderer's own CLIP
provider against that label, which sorts out wrong-subject results before anything is
downloaded in full. The score ranks candidates; the render gate still decides.

Output is one JSON object per candidate, ready to paste into ``sources`` of a topic spec.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shorts_studio.topic_builder import BOX_H, BOX_W, DEFAULT_NEGATIVE_LABELS, USER_AGENT, cache_path  # noqa: E402

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FREE_LICENCE = re.compile(r"^(public domain|pd\b|cc0|cc[ -]by([ -]sa)?[ -]\d)", re.IGNORECASE)
BROWSER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read())


def _text(markup: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", markup or ""))).strip()


def is_free_licence(short_name: str) -> bool:
    return bool(FREE_LICENCE.match((short_name or "").strip()))


def _clean_url(url: str) -> str:
    return url.split("?")[0]


def pick_rendition(original: dict, derivatives: list[dict]) -> dict:
    """The smallest Commons rendition that still fills the picture box.

    Originals are often 4K masters of several hundred megabytes. The 980x926
    picture needs 1080 pixels on the short side, so a 1080p rendition of the
    same file gives the same picture for a fraction of the download."""
    fits = [d for d in derivatives
            if d.get("width") and d.get("height") and min(int(d["width"]), int(d["height"])) >= 1080
            and "webm" in (d.get("type") or "")]
    if not fits or min(int(original["width"]), int(original["height"])) <= 1080:
        return {"url": _clean_url(original["url"]), "width": int(original["width"]), "height": int(original["height"])}
    best = min(fits, key=lambda d: int(d["width"]) * int(d["height"]))
    return {"url": _clean_url(best["src"]), "width": int(best["width"]), "height": int(best["height"])}


# Standard thumbnail width Wikimedia serves from its cache
# (https://www.mediawiki.org/wiki/Common_thumbnail_sizes). Large originals are
# rate limited per host: a 429 with "Retry-After: 600" stopped a timed
# production; the 1920 px thumbnail of the same file was served at once.
THUMB_WIDTH = 1920


def photo_rendition(info: dict) -> dict:
    """The 1920 px standard thumbnail of a large photo, if it still fills the picture.

    Kept at the original when the photo is no wider than the thumbnail, when
    the thumbnail would be shorter than the 926 px picture box (it would then
    be upscaled), or for formats whose thumbnails are re-encoded (TIFF)."""
    url, width, height = _clean_url(info["url"]), int(info.get("width") or 0), int(info.get("height") or 0)
    marker = "/wikipedia/commons/"
    name = url.rsplit("/", 1)[-1]
    if (width <= THUMB_WIDTH or marker not in url or name.lower().endswith((".tif", ".tiff"))
            or height * THUMB_WIDTH / width < BOX_H):
        return {"url": url, "width": width, "height": height}
    head, tail = url.split(marker, 1)
    return {"url": f"{head}{marker}thumb/{tail}/{THUMB_WIDTH}px-{name}", "width": THUMB_WIDTH,
            "height": round(height * THUMB_WIDTH / width)}


def commons_candidates(query: str, kind: str, limit: int, min_width: int) -> list[dict]:
    video = kind == "video"
    prefix = "vi" if video else "ii"
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": "6", "gsrlimit": str(limit),
        "gsrsearch": f"filetype:{'video' if video else 'bitmap'} {query}", "prop": "videoinfo" if video else "imageinfo",
        f"{prefix}prop": "url|size|mime|extmetadata" + ("|derivatives" if video else ""), f"{prefix}urlwidth": "1280",
        f"{prefix}extmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Credit",
    }
    pages = _get_json(COMMONS_API + "?" + urllib.parse.urlencode(params)).get("query", {}).get("pages", {})
    found = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (page.get("videoinfo" if video else "imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        licence = _text(meta.get("LicenseShortName", {}).get("value", ""))
        if not info.get("url") or not is_free_licence(licence) or int(info.get("width", 0)) < min_width:
            continue
        artist = _text(meta.get("Artist", {}).get("value", "")) or _text(meta.get("Credit", {}).get("value", ""))
        chosen = pick_rendition(info, info.get("derivatives") or []) if video else photo_rendition(info)
        found.append({
            "kind": kind, "url": chosen["url"], "page": info.get("descriptionurl", ""),
            "attribution": f"{artist[:60] or 'Unknown author'} / Wikimedia Commons / {licence}",
            "license_url": _text(meta.get("LicenseUrl", {}).get("value", "")) or None,
            "_width": chosen["width"], "_height": chosen["height"],
            "_seconds": round(float(info.get("duration", 0) or 0), 1), "_preview": info.get("thumburl"),
            "_title": page.get("title"),
        })
    return found


def pexels_candidate(video_id: str) -> dict:
    """Resolve the MP4 that pexels.com's own download link redirects to."""
    req = urllib.request.Request(f"https://www.pexels.com/download/video/{video_id}/", method="HEAD",
                                 headers={"User-Agent": BROWSER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as response:
        url = response.geturl()
    if "videos.pexels.com" not in url or not url.lower().split("?")[0].endswith(".mp4"):
        raise RuntimeError(f"Pexels id {video_id} did not resolve to a video file: {url}")
    url = url.split("?")[0]
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
         "-of", "json", url], capture_output=True, text=True, check=True, timeout=90).stdout)
    stream = probe["streams"][0]
    return {"kind": "video", "url": url, "page": f"https://www.pexels.com/video/{video_id}/",
            "attribution": "<author> / Pexels / Pexels License", "license_url": "https://www.pexels.com/license/",
            "_width": stream["width"], "_height": stream["height"],
            "_seconds": round(float(probe["format"]["duration"]), 1), "_preview": url, "_title": f"pexels {video_id}"}


def clip_margin(candidate: dict, label: str, work: Path) -> float | None:
    """CLIP positive-minus-negative margin of the candidate's preview frame, boxed like the render."""
    from PIL import Image
    from shorts_studio.topic_builder import box_crop
    from shorts_studio.visual_qa import ClipSemanticVisionProvider
    raw = work / "preview.jpg"
    preview = candidate.get("_preview")
    if not preview:
        return None
    if candidate["kind"] == "video" and candidate["url"] == preview:
        seconds = min(2.0, max(0.0, candidate["_seconds"] / 3))
        done = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seconds:.2f}", "-i", preview,
                               "-frames:v", "1", "-q:v", "3", str(raw)], capture_output=True, timeout=120)
        if done.returncode != 0:
            return None
    else:
        req = urllib.request.Request(preview, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=45) as response:
            raw.write_bytes(response.read())
    picture = Image.open(raw).convert("RGB")
    w, h, x, y = box_crop(*picture.size)
    canvas = Image.new("RGB", (1080, 950), (0, 0, 0))
    canvas.paste(picture.crop((x, y, x + w, y + h)).resize((BOX_W, BOX_H), Image.LANCZOS), (50, 12))
    boxed = work / "boxed.jpg"
    canvas.save(boxed, quality=92)
    verdict = ClipSemanticVisionProvider().evaluate(boxed, [label], positive_labels=[label],
                                                    negative_labels=DEFAULT_NEGATIVE_LABELS, media_box_applied=True)
    margin = verdict.get("margin")
    return None if margin is None else round(margin, 4)


def cached_download(url: str, cache_dir: Path) -> Path:
    """Fetch a candidate once into the shared cache; the production reuses the same file."""
    from shorts_studio.topic_builder import _fetch, _validate_video
    target = cache_path(url, cache_dir)
    return _fetch(url, target, 300_000, _validate_video)


def preview_sheet(source: str, out: Path, frames: int = 8) -> dict:
    """Tile evenly spaced frames (time stamped) from a video; returns its size and duration."""
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "json", source],
        capture_output=True, text=True, check=True, timeout=120).stdout)
    duration = float(probe["format"]["duration"])
    stream = probe["streams"][0]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stills = []
        for i in range(frames):
            seconds = duration * (i + 0.5) / frames
            still = Path(tmp) / f"{i:02d}.jpg"
            # drawtext needs a font file on some builds; the time goes in the file order instead.
            done = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seconds:.2f}",
                                   "-i", source, "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(still)],
                                  capture_output=True, timeout=180)
            if done.returncode == 0 and still.is_file():
                stills.append((seconds, still))
        if not stills:
            raise RuntimeError(f"no frame could be read from {source}")
        if len(stills) == 1:
            out.write_bytes(stills[0][1].read_bytes())
            return {"sheet": str(out), "width": stream["width"], "height": stream["height"],
                    "seconds": round(duration, 2), "frame_times": [round(stills[0][0], 2)]}
        columns = min(4, len(stills))
        inputs = [x for _, f in stills for x in ("-i", str(f))]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                        "".join(f"[{i}:v]" for i in range(len(stills)))
                        + f"xstack=inputs={len(stills)}:grid={columns}x{-(-len(stills) // columns)}:fill=black[v]",
                        "-map", "[v]", "-frames:v", "1", "-q:v", "4", str(out)], check=True, capture_output=True, timeout=120)
    return {"sheet": str(out), "width": stream["width"], "height": stream["height"], "seconds": round(duration, 2),
            "frame_times": [round(t, 2) for t, _ in stills]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="provider", required=True)
    commons = sub.add_parser("commons")
    commons.add_argument("query")
    commons.add_argument("--kind", choices=["video", "photo"], default="video")
    commons.add_argument("--limit", type=int, default=20)
    commons.add_argument("--min-width", type=int, default=1000)
    pexels = sub.add_parser("pexels")
    pexels.add_argument("ids", nargs="+")
    preview = sub.add_parser("preview")
    preview.add_argument("source")
    preview.add_argument("--out", type=Path, required=True)
    preview.add_argument("--frames", type=int, default=8)
    preview.add_argument("--cache", type=Path, default=REPO / "build" / "footage_cache")
    for parser in (commons, pexels):
        parser.add_argument("--label", default=None, help="CLIP label to rank candidates by")
    args = ap.parse_args()

    if args.provider == "preview":
        # A remote file is downloaded once and read locally: seeking over HTTP
        # sends a burst of range requests, which Wikimedia answers with a 10-minute 429.
        local = str(cached_download(args.source, args.cache)) if args.source.startswith("http") else args.source
        print(json.dumps({**preview_sheet(local, args.out, args.frames), "local": local}))
        return 0
    if args.provider == "commons":
        candidates = commons_candidates(args.query, args.kind, args.limit, args.min_width)
    else:
        candidates = []
        for video_id in args.ids:
            try:
                candidates.append(pexels_candidate(video_id))
            except Exception as exc:
                print(json.dumps({"_title": f"pexels {video_id}", "_error": str(exc)[:200]}), flush=True)
    if args.label:
        with tempfile.TemporaryDirectory() as tmp:
            for candidate in candidates:
                try:
                    candidate["_clip_margin"] = clip_margin(candidate, args.label, Path(tmp))
                except Exception as exc:
                    candidate["_clip_margin"] = None
                    candidate["_clip_error"] = str(exc)[:120]
        candidates.sort(key=lambda c: -(c.get("_clip_margin") or -1.0))
    for candidate in candidates:
        print(json.dumps(candidate, ensure_ascii=False), flush=True)
    return 0 if candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
