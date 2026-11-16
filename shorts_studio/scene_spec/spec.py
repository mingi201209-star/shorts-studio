"""Scene execution spec: turns a narration script into structured, machine-checkable scene definitions ("말하는 그대로 보여줘라").

Every narration sentence (or clause) is a Scene: the exact words, the spoken cue that starts it, the objects that must be on screen, the PHYSICAL PHENOMENON that must happen
(with the telemetry metric that proves it), the camera, the effects, and the success conditions. A scene that only has narration and no phenomenon definition is rejected by
`validate`; a scene whose phenomenon needs a capability the renderer does not have yet is rejected for production (`production_blockers`). Independent module: no Blender, no
dependency on the render pipeline. Times are NOT stored here: they are resolved from the real TTS cue timing (`alignment.resolve_windows`)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: check kinds the alignment evaluator understands. "manual" is never decided automatically (reported NOT_VERIFIED).
CHECK_KINDS = ("metric_increase", "metric_reaches", "metric_at_most", "metric_at_least", "onset_near_cue", "onset_within_s", "subjects_in_view", "ordered_onsets", "not_obscured", "manual")
#: the six alignment criteria of the owner's directive
CRITERIA = ("subject_present", "action_performed", "timing", "sound_off_understandable", "physically_consistent", "not_obscured")


@dataclass
class Check:
    id: str
    description: str
    kind: str
    criterion: str                          # one of CRITERIA
    metric: str = ""
    value: float = 0.0                      # threshold / delta / seconds / tolerance, by kind
    first: str = ""                         # ordered_onsets: this onset must come first ...
    second: str = ""                        # ... before this one
    subjects: list[str] = field(default_factory=list)
    window: str = "scene"                   # "scene" or "first_<n>s" (n seconds from the scene start)
    onset_threshold: float = 0.0            # metric level that counts as "has started"

    @staticmethod
    def from_dict(d: dict) -> "Check":
        return Check(**d)


@dataclass
class Phenomenon:
    kind: str                               # capability name, e.g. structure_deformation
    description: str                        # what physically happens (not what is shown)
    onset_metric: str                       # telemetry metric whose first rise marks the start of the phenomenon
    onset_threshold: float
    explanation_only: bool = False          # True if it is an explanatory visualisation, not simulated physics

    @staticmethod
    def from_dict(d: dict) -> "Phenomenon":
        return Phenomenon(**d)


@dataclass
class Scene:
    id: str
    beat: int
    narration: str                          # the exact spoken sentence (or clause of a sentence)
    cue: str                                # exact text of the caption cue at which this scene's picture must start
    subjects: list[str]                     # objects / parts that must be on screen
    phenomenon: Phenomenon
    camera: dict                            # {"kind": ..., "movement": ...}
    effects: list[str]                      # capability names: xray_reveal, structure_folding, ...
    success: list[Check]
    silent_readable: bool = True            # must be understandable with the sound off (checked by a person: NOT_VERIFIED here)

    @staticmethod
    def from_dict(d: dict) -> "Scene":
        d = dict(d)
        d["phenomenon"] = Phenomenon.from_dict(d["phenomenon"])
        d["success"] = [Check.from_dict(c) for c in d["success"]]
        return Scene(**d)


@dataclass
class EpisodeSpec:
    episode: str
    title: str
    target_seconds: float
    narration: list[str]                    # the full narration, one entry per spoken beat (must match the speech plan)
    scenes: list[Scene]
    assumptions: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "EpisodeSpec":
        d = dict(d)
        d["scenes"] = [Scene.from_dict(s) for s in d["scenes"]]
        return EpisodeSpec(**d)


def load_spec(path: str | Path) -> EpisodeSpec:
    return EpisodeSpec.from_dict(json.loads(Path(path).read_text(encoding="utf8")))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate(spec: EpisodeSpec, speech_plan_beats: list[str] | None = None) -> list[str]:
    """Structural problems that stop a spec from being handed to the render department. An empty list means the spec is complete, not that the picture is right."""
    problems = []
    ids = [s.id for s in spec.scenes]
    if len(ids) != len(set(ids)):
        problems.append("scene ids are not unique")
    for s in spec.scenes:
        p = f"scene {s.id}: "
        if not _norm(s.narration):
            problems.append(p + "no narration")
        if not s.cue.strip() or s.cue.strip() not in s.narration:
            problems.append(p + "cue must be words taken from the scene's narration")
        if not s.subjects:
            problems.append(p + "no subjects (what must be on screen)")
        if not s.phenomenon.description.strip() or not s.phenomenon.onset_metric.strip():
            problems.append(p + "no physical phenomenon with an onset metric: a narration-only scene is not production material")
        if not s.camera.get("kind"):
            problems.append(p + "no camera")
        if not s.effects:
            problems.append(p + "no effects (even plain 'none' must be stated explicitly)")
        if not s.success:
            problems.append(p + "no success conditions")
        covered = {c.criterion for c in s.success}
        for need in ("subject_present", "action_performed", "timing"):
            if need not in covered:
                problems.append(p + f"no success condition for criterion {need!r}")
        for c in s.success:
            if c.kind not in CHECK_KINDS:
                problems.append(p + f"check {c.id}: unknown kind {c.kind!r}")
            if c.criterion not in CRITERIA:
                problems.append(p + f"check {c.id}: unknown criterion {c.criterion!r}")
    if speech_plan_beats is not None:
        spoken = _norm(" ".join(speech_plan_beats))
        written = _norm(" ".join(s.narration for s in sorted(spec.scenes, key=lambda s: s.beat)))
        if spoken != written:
            problems.append("the scenes do not cover the narration exactly (words missing, added or reordered)")
        if [_norm(b) for b in speech_plan_beats] != [_norm(b) for b in spec.narration]:
            problems.append("spec.narration differs from the speech plan")
        beats = sorted({s.beat for s in spec.scenes})
        if beats != list(range(1, len(speech_plan_beats) + 1)):
            problems.append("some narration beat has no scene")
    return problems


def production_blockers(spec: EpisodeSpec, capabilities: dict[str, bool]) -> list[str]:
    """What the renderer cannot do yet: every phenomenon kind and effect a scene needs must be an implemented capability."""
    out = []
    for s in spec.scenes:
        for name in dict.fromkeys([s.phenomenon.kind, *s.effects]):
            if name == "none":
                continue
            if not capabilities.get(name, False):
                out.append(f"scene {s.id}: capability {name!r} is not implemented")
    return out
