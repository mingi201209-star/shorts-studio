"""Declarative topic production: one JSON topic spec -> prepared assets + a strict manifest.

Before this module every Short had its own ~450-line ``scripts/build_<topic>_states.py``
that re-implemented the same steps (pinned downloads, FFmpeg clip preparation, hook
selection, beat/production tagging, manifest assembly). Writing and debugging that file
was the largest part of producing a new topic. Here the topic-specific part is data
(``TopicSpec``) and the steps are shared, timed stages, so a new topic does not need new
engine code.

The output is an ordinary manifest for the unchanged ``shorts_studio render``: the same
strict contracts (meaningful visual changes, retention contract, Visual Production V2),
the same per-beat CLIP labels and pinned content hashes. Nothing here evaluates quality;
every gate stays in the renderer and runs unmodified.

Media handling is FFmpeg (the same filter chain the hydroplaning builder uses) and
Pillow. Callout labels on real footage are drawn once with Pillow and composited by
FFmpeg's ``overlay``/``fade`` filters; there is no custom per-frame renderer.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hook_studio import (
    HookCandidate, TopicBrief, build_story_generation_prompt, generate_and_judge,
    story_writer_system_prompt,
)

# Picture size inside shorts_studio.render's 980x950 media box. 12 px of black stays
# above/below so the picture never reaches the title gate's row band
# (final_video_qa.TITLE_ROW_BAND ends 10 px inside the box). Same value as the
# hydroplaning builder, which established it against the real gate.
BOX_W, BOX_H = 980, 926
HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}
BT709_TAGS = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
DEFAULT_NEGATIVE_LABELS = ["a photograph of a cat", "a landscape photograph of mountains", "a city skyline"]
USER_AGENT = "shorts-studio/0.1 (licensed production asset)"
# Prepared pictures are intermediates: the renderer encodes them again. Measured on a
# real 1080p aurora clip against a lossless reference of the same filter chain, veryfast
# at CRF 14 is at least as faithful as the hydroplaning builder's slow at CRF 16
# (SSIM 0.98813 vs 0.98750, PSNR 38.81 vs 38.78 dB) and three times faster (12 s vs 36 s).
X264_INTERMEDIATE = ["-preset", "veryfast", "-crf", "14"]
FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
)

_FORBID = ConfigDict(extra="forbid")


class SourceSpec(BaseModel):
    """One pinned, explicitly licensed source file."""
    model_config = _FORBID
    kind: Literal["video", "photo"]
    url: str = Field(min_length=8, description="concrete file URL, never a search or listing page")
    page: str = Field(min_length=8, description="the human-readable landing page that states the licence")
    attribution: str = Field(min_length=3, description="author / site / licence, as shown in the description")
    license_url: str | None = None


class ClipSpec(BaseModel):
    """One beat-sized picture cut from a source to exactly fill the media box.

    ``crop`` is ``w:h:x:y`` in source pixels. Leave it out to take the largest
    box-aspect window, positioned by ``focus`` (0..1 across the free axis)."""
    model_config = _FORBID
    source: str
    start: float = Field(default=0.0, ge=0.0)
    seconds: float = Field(default=6.0, gt=0.5, le=20.0)
    slowmo: float = Field(default=1.0, ge=1.0, le=4.0)
    crop: str | None = None
    focus: tuple[float, float] = (0.5, 0.5)


class CalloutSpec(BaseModel):
    """A label with a leader line to the thing it names, in media-box pixels."""
    model_config = _FORBID
    text: str = Field(min_length=1, max_length=14)
    at: tuple[int, int] = Field(description="label centre (x, y) inside the 980x926 picture")
    target: tuple[int, int] = Field(description="the point the leader line ends on")
    appear: float = Field(default=0.3, ge=0.0, description="seconds into the clip the label fades in")
    color: str = "#FFC857"


class OverlaySpec(BaseModel):
    """Real footage or a real photo with callout labels: the mechanism shown on the evidence itself."""
    model_config = _FORBID
    base: str = Field(description="key of the clip the labels are drawn on")
    callouts: list[CalloutSpec] = Field(min_length=1, max_length=4)
    headline: str | None = Field(default=None, max_length=16)


class BeatSpec(BaseModel):
    model_config = _FORBID
    asset: str = Field(description="key of a clip or an overlay")
    cue: str = Field(min_length=2, description="narration words this picture starts on")
    info_role: str = Field(min_length=3, description="what this picture adds; unique in the video")
    concept_id: str
    state_id: str
    kind: Literal["concept", "state"] = "concept"
    qa_label: str = Field(min_length=12, description="English CLIP label describing what must be visible")
    requirement: str = Field(min_length=8, description="Korean statement of what the picture must show")
    role: Literal["hero", "evidence", "mechanism", "second_peak", "payoff", "support"]
    visual_mode: Literal["real_footage", "real_photo", "physical_animation", "mechanism_overlay", "evidence_graphic"]
    negative_labels: list[str] | None = None


class PhraseSpec(BaseModel):
    model_config = _FORBID
    role: str
    text: str = Field(min_length=2)


class SceneSpec(BaseModel):
    model_config = _FORBID
    id: str
    phrases: list[PhraseSpec] = Field(min_length=1)
    beats: list[BeatSpec] = Field(min_length=1)


class TopicSpec(BaseModel):
    model_config = _FORBID
    topic_id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    overlay_title: str
    brief: TopicBrief
    hooks: dict[str, str] = Field(description="strategy -> candidate hook sentence; the rule-based judge picks one")
    uncertainty_notes: list[str] = Field(default_factory=list)
    observable_phenomenon: str
    silent_story: str
    visual_description: str
    scene_requirement: str = Field(description="Korean scene-level requirement used for every scene")
    sources: dict[str, SourceSpec]
    clips: dict[str, ClipSpec]
    overlays: dict[str, OverlaySpec] = Field(default_factory=dict)
    scenes: list[SceneSpec] = Field(min_length=2)
    fact_sources: list[str] = Field(min_length=1, description="where the stated facts come from (name + URL)")
    description_notes: list[str] = Field(default_factory=list)
    tts_continuity_mode: str = "scene_continuous"

    @model_validator(mode="after")
    def _references_resolve(self):
        if self.brief.topic_id != self.topic_id:
            raise ValueError("brief.topic_id must equal topic_id")
        for key, clip in self.clips.items():
            if clip.source not in self.sources:
                raise ValueError(f"clip {key!r} uses unknown source {clip.source!r}")
        clash = set(self.clips) & set(self.overlays)
        if clash:
            raise ValueError(f"keys used for both a clip and an overlay: {sorted(clash)}")
        for key, overlay in self.overlays.items():
            if overlay.base not in self.clips:
                raise ValueError(f"overlay {key!r} is drawn on unknown clip {overlay.base!r}")
        known = set(self.clips) | set(self.overlays)
        used = []
        for scene in self.scenes:
            for beat in scene.beats:
                if beat.asset not in known:
                    raise ValueError(f"{scene.id}: beat uses unknown asset {beat.asset!r}")
                used.append(beat.asset)
        if len(used) != len(set(used)):
            # One prepared picture per beat: a repeated picture is the cheap
            # "same shot again" the source-reuse gates exist to stop.
            raise ValueError("every beat needs its own clip or overlay; an asset key is used twice")
        if self.scenes[0].phrases[0].role != "HOOK":
            raise ValueError("the first phrase of the first scene must be the HOOK; its text is replaced by the judged hook")
        return self


def load_topic(path: str | Path) -> TopicSpec:
    return TopicSpec.model_validate_json(Path(path).read_text(encoding="utf-8"))


class StageTimer:
    """Wall-clock stage log. Every production writes it next to its outputs so
    the time budget is a measurement, not an estimate."""

    def __init__(self) -> None:
        self.started = time.time()
        self.stages: list[dict] = []

    def run(self, name: str, fn, *args, **kwargs):
        t0 = time.time()
        try:
            return fn(*args, **kwargs)
        finally:
            seconds = round(time.time() - t0, 2)
            self.stages.append({"stage": name, "seconds": seconds})
            print(f"[stage] {name}: {seconds:.1f}s (elapsed {time.time() - self.started:.0f}s)", flush=True)

    def report(self) -> dict:
        return {"started_unix": round(self.started, 2), "total_seconds": round(time.time() - self.started, 2),
                "stages": list(self.stages)}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Hosts that throttle parallel or repeated requests. Wikimedia answers a burst
# with 429 and "Retry-After: 600", which no 30-minute production can wait out,
# so these are fetched strictly one at a time and never re-requested.
_ONE_AT_A_TIME_HOSTS = ("wikimedia.org",)
_MAX_RETRY_AFTER_SECONDS = 60


def cache_path(url: str, cache_dir: Path) -> Path:
    """Where a pinned URL lives in the shared download cache."""
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return cache_dir / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:24] + suffix)


def _fetch(url: str, out: Path, minimum_bytes: int, validate, cache_dir: Path | None = None) -> Path:
    """Fetch one pinned file with bounded retries; fail closed on a response
    that is too small or the wrong container, so a broken source can never
    silently become a placeholder. A file already fetched for previewing is
    taken from ``cache_dir`` instead of being requested a second time."""
    if out.is_file() and out.stat().st_size >= minimum_bytes:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    cached = cache_path(url, cache_dir) if cache_dir else None
    if cached and cached.is_file() and cached.stat().st_size >= minimum_bytes:
        validate(cached.read_bytes())
        shutil.copyfile(cached, out)
        return out
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
            if len(data) < minimum_bytes:
                raise RuntimeError(f"download suspiciously small: {len(data)} bytes")
            validate(data)
            partial = out.with_suffix(out.suffix + ".part")
            partial.write_bytes(data)
            partial.replace(out)
            if cached:
                cached.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out, cached)
            return out
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                wait = int(exc.headers.get("Retry-After") or 0)
                if wait > _MAX_RETRY_AFTER_SECONDS:
                    raise RuntimeError(f"{urllib.parse.urlparse(url).netloc} is rate limiting this host for {wait}s; "
                                       f"use another source for {url} or retry later") from exc
                time.sleep(max(wait, 5))
            elif exc.code in (403, 404, 410):
                break  # a permanent refusal never succeeds on retry
            elif attempt < 3:
                time.sleep(5 * (attempt + 1))
        except Exception as exc:  # network and validation failures retry alike
            last = exc
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch required source {url}: {last}")


def _validate_video(data: bytes) -> None:
    head = data[:64]
    # ISO-BMFF stores an ftyp box near the start; WebM/Matroska and Ogg (the
    # containers Wikimedia Commons serves) have their own magic numbers.
    if not (b"ftyp" in head or head.startswith(b"\x1a\x45\xdf\xa3") or head.startswith(b"OggS")):
        raise RuntimeError("response is not an MP4, WebM or Ogg video")


def _validate_photo(data: bytes) -> None:
    import io
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        image.verify()


def fetch_sources(spec: TopicSpec, source_dir: Path, cache_dir: Path | None = None) -> dict[str, Path]:
    def one(item):
        key, src = item
        suffix = Path(urllib.parse.urlparse(src.url).path).suffix.lower() or (".mp4" if src.kind == "video" else ".jpg")
        if src.kind == "video":
            return key, _fetch(src.url, source_dir / f"{key}{suffix}", 300_000, _validate_video, cache_dir)
        return key, _fetch(src.url, source_dir / f"{key}{suffix}", 20_000, _validate_photo, cache_dir)

    def throttled(item) -> bool:
        return any(host in urllib.parse.urlparse(item[1].url).netloc for host in _ONE_AT_A_TIME_HOSTS)
    items = list(spec.sources.items())
    with ThreadPoolExecutor(max_workers=6) as pool:
        parallel = pool.map(one, [i for i in items if not throttled(i)])
        serial = [one(i) for i in items if throttled(i)]
        return {**dict(parallel), **dict(serial)}


def _recipe_path(out: Path) -> Path:
    return out.with_name(out.name + ".recipe.json")


def _is_current(out: Path, recipe: dict, minimum_bytes: int) -> bool:
    """A prepared file is reused only if it was made from this exact recipe.

    Re-running a topic after editing a clip's trim, crop or callouts must
    rebuild that picture; reusing a file by name alone would put the old
    picture on screen with the new labels and hashes."""
    if not (out.is_file() and out.stat().st_size > minimum_bytes):
        return False
    try:
        return json.loads(_recipe_path(out).read_text(encoding="utf-8")) == recipe
    except (OSError, ValueError):
        return False


def _record_recipe(out: Path, recipe: dict) -> None:
    _recipe_path(out).write_text(json.dumps(recipe, sort_keys=True), encoding="utf-8")


def _probe_video(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,color_transfer:stream_side_data=rotation:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    stream = data["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    rotation = 0
    for side in stream.get("side_data_list", []) or []:
        rotation = int(side.get("rotation", 0) or 0)
    if abs(rotation) in (90, 270):
        width, height = height, width  # FFmpeg auto-rotates on decode
    return {"width": width, "height": height, "transfer": stream.get("color_transfer", ""),
            "duration": float(data.get("format", {}).get("duration", 0.0) or 0.0)}


def box_crop(width: int, height: int, focus: tuple[float, float] = (0.5, 0.5)) -> tuple[int, int, int, int]:
    """Largest window with the media-box aspect, slid along the free axis by ``focus``."""
    aspect = BOX_W / BOX_H
    if width / height >= aspect:
        crop_h = height - height % 2
        crop_w = min(width, int(round(crop_h * aspect)) // 2 * 2)
    else:
        crop_w = width - width % 2
        crop_h = min(height, int(round(crop_w / aspect)) // 2 * 2)
    x = int(round((width - crop_w) * min(max(focus[0], 0.0), 1.0)))
    y = int(round((height - crop_h) * min(max(focus[1], 0.0), 1.0)))
    return crop_w, crop_h, x, y


def _resolved_crop(clip: ClipSpec, width: int, height: int) -> str:
    if clip.crop:
        w, h, x, y = (int(v) for v in clip.crop.split(":"))
        if x + w > width or y + h > height:
            raise ValueError(f"crop {clip.crop} leaves the {width}x{height} source")
        if abs(w / h - BOX_W / BOX_H) > 0.02:
            raise ValueError(f"crop {clip.crop} is not the {BOX_W}:{BOX_H} media-box aspect; the picture would be distorted")
        return clip.crop
    return ":".join(str(v) for v in box_crop(width, height, clip.focus))


def prepare_video_clip(src: Path, out: Path, clip: ClipSpec) -> Path:
    """Trim + crop + scale one real clip to exactly fill the media box.

    One FFmpeg pass (HDR tone-map when the source is HLG/PQ, trim, crop, Lanczos
    scale, constant 30 fps, H.264 CRF 16, BT.709 tags, no audio) -- the chain the
    hydroplaning builder established, with a faster encoder setting of equal
    fidelity (see X264_INTERMEDIATE). Fails closed if the result is shorter than
    asked. ``slowmo=2`` plays a 60 fps source at half speed: no invented frames."""
    recipe = {"source": sha256(src), "clip": clip.model_dump(mode="json"), "encoder": X264_INTERMEDIATE}
    if _is_current(out, recipe, 100_000):
        return out
    info = _probe_video(src)
    need = clip.start + clip.seconds / clip.slowmo
    if info["duration"] and need > info["duration"] + 0.05:
        raise ValueError(f"{src.name}: clip needs {need:.2f}s of source but it is {info['duration']:.2f}s long")
    crop = _resolved_crop(clip, info["width"], info["height"])
    if info["transfer"] in HDR_TRANSFERS:
        # HDR (HLG/PQ) -> SDR BT.709 with FFmpeg's documented zscale+tonemap chain.
        to_sdr = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                  "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")
    else:
        to_sdr = "scale=out_color_matrix=bt709:out_range=tv,"
    partial = out.with_name(out.stem + ".part.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{clip.start:.3f}", "-t", f"{clip.seconds / clip.slowmo:.3f}",
        "-i", str(src),
        "-vf", f"{to_sdr}crop={crop},scale={BOX_W}:{BOX_H}:flags=lanczos,setsar=1,setpts={clip.slowmo}*PTS,fps=30,format=yuv420p",
        "-an", "-c:v", "libx264", *X264_INTERMEDIATE, *BT709_TAGS, "-movflags", "+faststart", str(partial),
    ], check=True, capture_output=True, timeout=300)
    duration = _probe_video(partial)["duration"]
    if duration < clip.seconds - 0.2:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"prepared clip {out.name} is {duration:.2f}s, shorter than the {clip.seconds}s asked")
    partial.replace(out)
    _record_recipe(out, recipe)
    return out


def prepare_photo(src: Path, out: Path, clip: ClipSpec) -> Path:
    """Crop a real photo to the box aspect at twice the box resolution."""
    recipe = {"source": sha256(src), "clip": clip.model_dump(mode="json")}
    if _is_current(out, recipe, 20_000):
        return out
    from PIL import Image, ImageOps
    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        w, h, x, y = (int(v) for v in _resolved_crop(clip, *image.size).split(":"))
        if w < BOX_W or h < BOX_H:
            raise ValueError(f"{src.name}: the {w}x{h} crop is smaller than the {BOX_W}x{BOX_H} picture; it would be upscaled and soft")
        image.crop((x, y, x + w, y + h)).resize((BOX_W * 2, BOX_H * 2), Image.LANCZOS).save(out, "JPEG", quality=93)
    _record_recipe(out, recipe)
    return out


# Seconds of picture prepared beyond a beat's measured time on screen. The
# render synthesizes the same text again, so its beat lengths match the
# preflight to within a few frames; a full second covers that with room.
HOLD_MARGIN_SECONDS = 1.0


def asset_holds(spec: TopicSpec, timing: dict) -> dict[str, float]:
    """Measured seconds on screen for every clip, from the narration preflight.

    An overlay's base clip is on screen for the overlay's beat."""
    beats = [beat for scene in spec.scenes for beat in scene.beats]
    if len(beats) != len(timing["beats"]):
        raise ValueError(f"{len(timing['beats'])} measured beats for {len(beats)} declared beats")
    holds = {}
    for beat, measured in zip(beats, timing["beats"]):
        key = spec.overlays[beat.asset].base if beat.asset in spec.overlays else beat.asset
        holds[key] = max(holds.get(key, 0.0), float(measured["seconds"]))
    return holds


def trimmed(clip: ClipSpec, hold: float | None) -> ClipSpec:
    """The clip cut to what the beat shows, never longer than authored.

    Encoding and decoding cost scale with the seconds prepared; a 6 s default
    for a 2.4 s beat spent most of the clip-preparation stage on frames that
    never reach the screen."""
    if hold is None:
        return clip
    return clip.model_copy(update={"seconds": round(min(clip.seconds, max(hold + HOLD_MARGIN_SECONDS, 1.5)), 2)})


def prepare_clips(spec: TopicSpec, raw: dict[str, Path], assets: Path,
                  holds: dict[str, float] | None = None) -> dict[str, Path]:
    """Prepare every clip. FFmpeg jobs run side by side; each is one process
    that already uses several threads, so three at a time fills a 4-core box."""
    assets.mkdir(parents=True, exist_ok=True)
    holds = holds or {}

    def one(item):
        key, clip = item
        clip = trimmed(clip, holds.get(key))
        if spec.sources[clip.source].kind == "photo":
            return key, prepare_photo(raw[clip.source], assets / f"{key}.jpg", clip)
        return key, prepare_video_clip(raw[clip.source], assets / f"{key}.mp4", clip)
    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(one, spec.clips.items()))


def _font(size: int, font_path: str | None = None):
    from PIL import ImageFont
    for candidate in ([font_path] if font_path else []) + list(FONT_CANDIDATES):
        if candidate and Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    raise RuntimeError("no Korean-capable font found; pass --font (callout labels must not fall back to tofu boxes)")


def render_callout_layer(callout: CalloutSpec, out: Path, font_path: str | None = None) -> Path:
    """One transparent box-sized PNG: a leader line, a target dot and a label
    on a dark rounded plate. Drawn at 2x and reduced for clean edges."""
    from PIL import Image, ImageDraw
    scale = 2
    layer = Image.new("RGBA", (BOX_W * scale, BOX_H * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(46 * scale, font_path)
    cx, cy = callout.at[0] * scale, callout.at[1] * scale
    tx, ty = callout.target[0] * scale, callout.target[1] * scale
    left, top, right, bottom = draw.textbbox((0, 0), callout.text, font=font)
    tw, th = right - left, bottom - top
    pad_x, pad_y = 22 * scale, 14 * scale
    plate = (cx - tw // 2 - pad_x, cy - th // 2 - pad_y, cx + tw // 2 + pad_x, cy + th // 2 + pad_y)
    if plate[0] < 8 * scale or plate[2] > (BOX_W - 8) * scale or plate[1] < 40 * scale or plate[3] > (BOX_H - 24) * scale:
        raise ValueError(f"callout {callout.text!r} does not fit inside the picture at {callout.at}")
    # Leader starts at the plate edge nearest the target, so it never crosses the text.
    sx = min(max(tx, plate[0]), plate[2])
    sy = plate[3] if ty > plate[3] else (plate[1] if ty < plate[1] else cy)
    draw.line((sx, sy, tx, ty), fill=(0, 0, 0, 150), width=7 * scale)
    draw.line((sx, sy, tx, ty), fill=callout.color, width=3 * scale)
    r = 9 * scale
    draw.ellipse((tx - r - 3 * scale, ty - r - 3 * scale, tx + r + 3 * scale, ty + r + 3 * scale), fill=(0, 0, 0, 150))
    draw.ellipse((tx - r, ty - r, tx + r, ty + r), fill=callout.color)
    draw.rounded_rectangle(plate, radius=16 * scale, fill=(12, 16, 24, 205), outline=callout.color, width=2 * scale)
    draw.text((cx - tw // 2 - left, cy - th // 2 - top), callout.text, font=font, fill=callout.color)
    layer.resize((BOX_W, BOX_H), Image.LANCZOS).save(out)
    return out


def render_headline_layer(text: str, out: Path, font_path: str | None = None) -> Path:
    from PIL import Image, ImageDraw
    scale = 2
    layer = Image.new("RGBA", (BOX_W * scale, BOX_H * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(64 * scale, font_path)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    cx, cy = BOX_W * scale // 2, 110 * scale
    plate = (cx - tw // 2 - 34 * scale, cy - th // 2 - 20 * scale, cx + tw // 2 + 34 * scale, cy + th // 2 + 20 * scale)
    if plate[0] < 8 * scale or plate[2] > (BOX_W - 8) * scale:
        raise ValueError(f"headline {text!r} is too wide for the picture")
    draw.rounded_rectangle(plate, radius=22 * scale, fill=(12, 16, 24, 215))
    draw.text((cx - tw // 2 - left, cy - th // 2 - top), text, font=font, fill="#FFFFFF")
    layer.resize((BOX_W, BOX_H), Image.LANCZOS).save(out)
    return out


def render_overlay_clip(base: Path, overlay: OverlaySpec, out: Path, work: Path, font_path: str | None = None) -> Path:
    """Composite the callout layers onto the prepared base with FFmpeg.

    Each layer fades in at its own time and then stays, so the picture gains
    one named part at a time. The base picture itself is not re-cropped,
    zoomed or re-timed. A photo base becomes a 6 s still clip."""
    recipe = {"base": sha256(base), "overlay": overlay.model_dump(mode="json"), "font": font_path,
              "encoder": X264_INTERMEDIATE}
    if _is_current(out, recipe, 50_000):
        return out
    work.mkdir(parents=True, exist_ok=True)
    layers: list[tuple[Path, float]] = []
    for i, callout in enumerate(overlay.callouts):
        layers.append((render_callout_layer(callout, work / f"{out.stem}_callout{i}.png", font_path), callout.appear))
    if overlay.headline:
        layers.append((render_headline_layer(overlay.headline, work / f"{out.stem}_headline.png", font_path), 0.2))
    is_photo = base.suffix.lower() in {".jpg", ".jpeg", ".png"}
    seconds = 6.0 if is_photo else _probe_video(base)["duration"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    cmd += ["-loop", "1", "-framerate", "30", "-t", f"{seconds:.3f}", "-i", str(base)] if is_photo else ["-i", str(base)]
    for layer, _ in layers:
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{seconds:.3f}", "-i", str(layer)]
    chain = [f"[0:v]scale={BOX_W}:{BOX_H}:flags=lanczos,setsar=1,fps=30,format=yuv420p[b0]"]
    for i, (_, appear) in enumerate(layers, start=1):
        chain.append(f"[{i}:v]format=rgba,fade=t=in:st={appear:.2f}:d=0.35:alpha=1[l{i}]")
        chain.append(f"[b{i - 1}][l{i}]overlay=0:0:shortest=1:format=auto[b{i}]")
    chain.append(f"[b{len(layers)}]format=yuv420p[v]")
    partial = out.with_name(out.stem + ".part.mp4")
    cmd += ["-filter_complex", ";".join(chain), "-map", "[v]", "-an", "-c:v", "libx264", *X264_INTERMEDIATE,
            *BT709_TAGS, "-movflags", "+faststart", "-t", f"{seconds:.3f}", str(partial)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    partial.replace(out)
    _record_recipe(out, recipe)
    return out


def render_overlays(spec: TopicSpec, prepared: dict[str, Path], assets: Path, work: Path,
                    font_path: str | None = None) -> dict[str, Path]:
    rendered = {key: render_overlay_clip(prepared[overlay.base], overlay, assets / f"{key}.mp4", work, font_path)
                for key, overlay in spec.overlays.items()}
    if rendered:
        overlay_preview(rendered, work / "overlays_preview.jpg")
    return rendered


def overlay_preview(rendered: dict[str, Path], out: Path) -> Path:
    """Every labelled picture at the moment its last label has faded in, side by side.

    A leader line that ends on the wrong thing passes every gate (the gates
    check that labels are legible and the picture is the pinned source, not
    that the arrow points at the eye of the storm). This sheet is written
    before any vision check or render so the author can see it in seconds."""
    from PIL import Image
    tiles = []
    for key, clip in rendered.items():
        frame = out.with_name(f"{out.stem}_{key}.jpg")
        seconds = min(2.0, max(0.1, _probe_video(clip)["duration"] - 0.1))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seconds:.2f}", "-i", str(clip), "-frames:v", "1",
                        str(frame)], check=True, capture_output=True, timeout=60)
        tiles.append(Image.open(frame).convert("RGB").resize((BOX_W // 2, BOX_H // 2)))
    sheet = Image.new("RGB", (len(tiles) * (BOX_W // 2), BOX_H // 2))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, (i * (BOX_W // 2), 0))
    sheet.save(out, quality=88)
    return out


class _SpecHookGenerator:
    """Serves the authored candidates to the unchanged rule-based judge."""

    def __init__(self, hooks: dict[str, str]):
        self.hooks = hooks

    def generate(self, brief: TopicBrief) -> list[HookCandidate]:
        facts = brief.fact_by_strategy()
        missing = [s for s in self.hooks if not facts.get(s)]
        if missing:
            raise ValueError(f"hook strategies without a brief fact to ground them: {missing}")
        return [HookCandidate(strategy=s, text=t, grounded_in=facts[s]) for s, t in self.hooks.items()]


def select_hook(spec: TopicSpec) -> HookCandidate:
    result = generate_and_judge(spec.brief, generator=_SpecHookGenerator(spec.hooks))
    if result.winner is None:
        reasons = "; ".join(f"[{v.candidate.strategy}] {v.reason}" for v in result.verdicts)
        raise RuntimeError(f"no hook candidate for {spec.topic_id} passed the hook judge: {reasons}")
    return result.winner


def scene_narration(spec: TopicSpec, scene_index: int, hook: HookCandidate) -> str:
    phrases = [p.text for p in spec.scenes[scene_index].phrases]
    if scene_index == 0:
        phrases[0] = hook.text
    return " ".join(phrases)


def check_cues(spec: TopicSpec, hook: HookCandidate) -> None:
    """Each beat starts on words that are spoken exactly once in its scene.

    The renderer binds beats to these words on the measured timeline, and the
    visual-change audit fails a cue that is missing or ambiguous. The hook is
    chosen by the judge, so the opening cues are checked against the sentence
    that actually won, and the error names it."""
    problems = []
    for index, scene in enumerate(spec.scenes):
        narration = "".join(ch for ch in scene_narration(spec, index, hook) if ch.isalnum())
        for beat in scene.beats:
            cue = "".join(ch for ch in beat.cue if ch.isalnum())
            count = narration.count(cue) if cue else 0
            if count != 1:
                problems.append(f"{scene.id}: cue {beat.cue!r} occurs {count} time(s)")
    if problems:
        raise ValueError(f"beat cues do not match the narration (judged hook [{hook.strategy}]: {hook.text!r}): "
                         + "; ".join(problems))


def check_text_contracts(spec: TopicSpec, hook: HookCandidate) -> None:
    """Run the project's own text-level contracts before any media work.

    The retention contract, the Visual Production V2 structure and the
    visual-change declarations depend only on the script, the cues and the
    beat tags. Evaluating them on a draft manifest (placeholder picture
    hashes, never written to disk) turns a failure that used to surface
    after the downloads and encodes into one that surfaces in a second. The
    real manifest goes through the same contracts again in ``validate``."""
    from .final_video_qa import compute_source_reuse, verify_retention_contract, verify_source_reuse
    from .models import Project
    from .production_v2 import verify_visual_production_structure
    from .visual_change import audit_visual_changes
    draft = Project.model_validate(build_manifest(spec, None, hook))
    failures = []
    # The draft has no picture files yet; that one finding is expected here and
    # is enforced on the real manifest by ``validate``. Every other finding counts.
    declared = [f for f in audit_visual_changes(draft)["failures"] if "reviewed source hash" not in f]
    if declared:
        failures.append(f"visual changes: {declared}")
    structure = verify_visual_production_structure(draft)
    if structure["status"] != "PASS":
        failures.append(f"visual production v2: {structure['reason']}")
    # The final-video source_reuse gate groups beats into source families by
    # their asset names, so the draft (named after the same spec keys) gets the
    # same verdict now that the render would give after ten minutes.
    reuse = verify_source_reuse(compute_source_reuse(draft))
    if reuse["status"] != "PASS":
        failures.append(f"source reuse: {reuse['reason']} -- put a different source between them")
    retention = verify_retention_contract(draft)
    if retention["status"] != "PASS":
        failed = {k: v.get("reason") for k, v in retention["checks"].items() if v.get("status") == "FAIL"}
        failures.append(f"retention contract: {failed}")
    if failures:
        raise ValueError("the script does not pass the text contracts: " + " | ".join(failures))


MIN_BEAT_SECONDS = 1.2  # visual_change's "unreadably short state" floor


def check_narration_timing(spec: TopicSpec, hook: HookCandidate, work: Path) -> dict:
    """Synthesize the real narration and run the timing gates on it before any picture exists.

    Beat lengths come from where the cue words fall in the measured speech, so
    they cannot be known from the text. Without this step a beat held too long
    is first reported by the final-video QA, after the downloads, the encodes
    and a full render. This calls the renderer's own synthesis and cue binding
    and the project's own checks (cut cadence, first-10-seconds retention,
    Visual Production V2 timeline); it defines no limits of its own beyond
    quoting the readable-beat floor. The render synthesizes again and its
    gates remain the verdict."""
    from . import render as renderer
    from .final_video_qa import (
        compute_first_10s_narration_timeline, verify_first_10s_retention, verify_visual_cut_cadence,
    )
    from .models import Project
    from .narration import resolve_config
    from .production_v2 import verify_visual_production_timeline
    from .visual_change import resolve_visual_cues
    work.mkdir(parents=True, exist_ok=True)
    project = Project.model_validate(build_manifest(spec, None, hook))
    narration = resolve_config(project)
    renderer.prepare_short_take(project, work, narration)
    windows, beats, cursor = [], [], 0.0
    for index, scene in enumerate(project.scenes):
        _, duration, _, subtitle, _, units = renderer._synthesize_scene_audio(
            scene, work, enable_subtle_breaths=project.enable_subtle_breaths, breath_seed=index,
            tts_continuity_mode=project.tts_continuity_mode, narration=narration)
        if subtitle["status"] != "PASS":
            raise ValueError(f"{scene.id}: subtitle QA failed on the measured narration: {subtitle}")
        timing = json.loads((work / f"{scene.id}.timing.json").read_text(encoding="utf-8"))
        scene.visual_beats = resolve_visual_cues(scene, timing["words"], duration).visual_beats
        starts = [float(b.start) for b in scene.visual_beats] + [duration]
        for beat_index, (a, b) in enumerate(zip(starts, starts[1:])):
            beats.append({"beat": f"{scene.id}[{beat_index}]", "start": round(cursor + a, 2), "seconds": round(b - a, 2)})
        windows.append({"scene": scene.id, "start": cursor, "duration": duration, "narration_units": units})
        cursor += duration
    failures = []
    short = [b for b in beats if b["seconds"] < MIN_BEAT_SECONDS]
    if short:
        failures.append(f"beats shorter than {MIN_BEAT_SECONDS}s: {short}")
    cadence = verify_visual_cut_cadence(windows, project.scenes)
    if cadence["status"] != "PASS":
        failures.append(f"cut cadence: {cadence.get('failures')}")
    cuts = [b["start"] for b in beats if b["start"] > 0]
    retention = verify_first_10s_retention(compute_first_10s_narration_timeline(windows), cuts)
    if retention["status"] != "PASS":
        failures.append(f"first 10s retention: {retention.get('reason')}")
    production = verify_visual_production_timeline(project, windows, cursor)
    if production["status"] != "PASS":
        failures.append(f"visual production v2 timeline: {production.get('reason')}")
    result = {"status": "FAIL" if failures else "PASS", "seconds": round(cursor, 2), "beats": beats, "failures": failures}
    if failures:
        table = ", ".join(f"{b['beat']}={b['seconds']}s" for b in beats)
        raise ValueError("the measured narration does not pass the timing gates: " + " | ".join(failures)
                         + f" | measured beats: {table}")
    return result


def build_manifest(spec: TopicSpec, assets: dict[str, Path] | None, hook: HookCandidate) -> dict:
    """Assemble the manifest. ``assets=None`` builds the draft used by
    ``check_text_contracts``: same text and tags, placeholder pictures."""
    scenes = []
    for scene_index, scene in enumerate(spec.scenes):
        plan = []
        for phrase_index, phrase in enumerate(scene.phrases):
            entry = {"role": phrase.role, "text": phrase.text}
            if scene_index == 0 and phrase_index == 0:
                entry = {"role": "HOOK", "text": hook.text, "hook_type": hook.strategy}
            plan.append(entry)
        beats = []
        for beat_index, beat in enumerate(scene.beats):
            asset = assets[beat.asset] if assets is not None else Path(f"{beat.asset}.draft")
            digest = sha256(asset) if assets is not None else hashlib.sha256(beat.asset.encode("utf-8")).hexdigest()
            base_key = spec.overlays[beat.asset].base if beat.asset in spec.overlays else beat.asset
            source = spec.sources[spec.clips[base_key].source]
            beats.append({
                # Relative order only: the renderer binds each beat to its
                # narration_cue on the measured word timeline.
                "start": float(beat_index),
                "asset": str(asset),
                "attribution": source.attribution,
                "visual_change": {
                    "kind": beat.kind, "concept_id": beat.concept_id, "state_id": beat.state_id,
                    "narration_cue": beat.cue, "added_information": beat.info_role, "source_sha256": digest,
                },
                "visual_qa_requirements": [beat.requirement],
                "visual_qa_labels": [beat.qa_label],
                "visual_qa_negative_labels": beat.negative_labels or DEFAULT_NEGATIVE_LABELS,
                "visual_qa_expected_sha256": [digest],
                "info_role": beat.info_role,
                "production": {"role": beat.role, "visual_mode": beat.visual_mode, "added_information": beat.info_role},
            })
        scenes.append({
            "id": scene.id,
            "narration": " ".join(p["text"] for p in plan),
            "narration_plan": plan,
            "visual_description": spec.visual_description,
            "asset": beats[0]["asset"],
            "attribution": beats[0]["attribution"],
            "visual_beats": beats,
            "visual_qa_requirements": [spec.scene_requirement],
            "visual_qa_labels": [beats[0]["visual_qa_labels"][0]],
            "visual_qa_negative_labels": beats[0]["visual_qa_negative_labels"],
            "overlay_title": None,
            "overlay_title_seconds": 2.8 if scene_index == 0 else None,
        })
    return {
        "title": spec.title,
        "width": 1080, "height": 1920, "fps": 30,
        "overlay_title": spec.overlay_title,
        "overlay_title_mode": "first_scene_only",
        "tts_continuity_mode": spec.tts_continuity_mode,
        "max_visual_recovery_attempts": 2,
        "strict_source_diversity": False,
        "strict_meaningful_visual_changes": True,
        "strict_retention_contract": True,
        "strict_visual_production_v2": True,
        "observable_phenomenon": spec.observable_phenomenon,
        "silent_story": spec.silent_story,
        # Whether a muted viewer stays is a human judgment; the builder never claims it.
        "silent_interest_review": "pending",
        "strict_entertainment_contract": False,
        "scenes": scenes,
    }


def upload_description(spec: TopicSpec) -> str:
    """Credits and fact sources for the upload description (this repository never uploads)."""
    used = {spec.clips[(spec.overlays[b.asset].base if b.asset in spec.overlays else b.asset)].source
            for scene in spec.scenes for b in scene.beats}
    lines = [f"# {spec.title} — 출처", "", "실제 촬영 영상·사진 (잘라내기·크기 조정):"]
    for key, src in spec.sources.items():
        if key in used:
            licence = f", 라이선스: {src.license_url}" if src.license_url else ""
            lines.append(f"- {src.attribution} ({src.page}{licence})")
    if spec.overlays:
        lines += ["", "화면 위 이름표와 지시선은 이 영상을 위해 실제 영상·사진 위에 직접 얹은 설명용 표시입니다."]
    lines += ["", "내용 출처:"] + [f"- {s}" for s in spec.fact_sources]
    if spec.description_notes:
        lines += [""] + list(spec.description_notes)
    return "\n".join(lines) + "\n"


def build_topic(spec: TopicSpec, root: Path, font_path: str | None = None, timer: StageTimer | None = None,
                cache_dir: Path | None = None) -> dict:
    """Run every pre-render stage under ``root`` and write the manifest.

    Layout: ``root/assets/<topic>/`` (prepared pictures, ``sources/`` beneath),
    ``root/<topic>.json`` (manifest), ``root/<topic>_upload_description.txt``."""
    timer = timer or StageTimer()
    assets_dir = root / "assets" / spec.topic_id
    # Text first: the judge picks the hook and the cues are checked against the
    # narration in well under a second, before any download or encode is spent.
    hook = timer.run("select_hook", select_hook, spec)
    check_cues(spec, hook)
    timer.run("text_contracts", check_text_contracts, spec, hook)
    timing = timer.run("narration_timing", check_narration_timing, spec, hook, root / "work" / "narration_preflight")
    raw = timer.run("fetch_sources", fetch_sources, spec, assets_dir / "sources", cache_dir)
    prepared = timer.run("prepare_clips", prepare_clips, spec, raw, assets_dir, asset_holds(spec, timing))
    overlays = timer.run("render_overlays", render_overlays, spec, prepared, assets_dir, root / "work", font_path)
    manifest = build_manifest(spec, {**prepared, **overlays}, hook)
    manifest_path = root / f"{spec.topic_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / f"{spec.topic_id}_upload_description.txt").write_text(upload_description(spec), encoding="utf-8")
    (root / f"{spec.topic_id}_story_prompt.txt").write_text(
        story_writer_system_prompt() + "\n\n"
        + build_story_generation_prompt(spec.brief, hook, uncertainty_notes=spec.uncertainty_notes) + "\n",
        encoding="utf-8")
    return {"manifest": manifest_path, "hook": hook, "assets": {**prepared, **overlays}, "timer": timer,
            "narration_timing": timing}
