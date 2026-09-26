from pydantic import BaseModel, Field, model_validator

class Motion(BaseModel):
    type: str = "push_in"

class AssetCandidate(BaseModel):
    """A fallback asset the visual-QA recovery loop may swap in for a scene."""
    asset: str | None = None
    asset_url: str | None = None
    attribution: str | None = None

class VisualBeat(BaseModel):
    """An optional timed visual cut inside one narration scene."""
    start: float = Field(ge=0)
    asset: str | None = None
    asset_url: str | None = None
    attribution: str | None = None
    motion: Motion = Motion()
    visual_qa_requirements: list[str] = Field(default_factory=list)
    visual_qa_labels: list[str] = Field(default_factory=list)
    visual_qa_negative_labels: list[str] = Field(default_factory=list)
    visual_qa_expected_sha256: list[str] = Field(default_factory=list)

class NarrationPhrase(BaseModel):
    """One authored, role-tagged text segment of a scene's spoken delivery
    (see shorts_studio/prosody.py and shorts_studio/korean_boundary.py).
    Narrative role is an authorial/semantic decision (which part of the
    story this text plays), so it stays here; the actual pause placement
    and synthesis-unit grouping is NOT authored -- it is computed
    automatically from Korean grammatical structure by korean_boundary.py,
    so the same text always segments the same way regardless of which
    script it appears in. `pace` is a narrow escape hatch for an explicit
    rate override; there is deliberately no boundary/pause field here."""
    role: str  # HOOK|SETUP|CRISIS|INVESTIGATION|REVEAL|EXPLANATION|PAYOFF
    text: str = Field(min_length=1)
    focus: bool = False  # the emphasis/result target, e.g. a REVEAL's delivered payload
    pace: str | None = None  # optional explicit Edge TTS rate override, e.g. "+2%"

class Scene(BaseModel):
    id: str
    narration: str = Field(min_length=1)
    visual_description: str = Field(min_length=1)
    asset: str | None = None
    asset_url: str | None = None
    attribution: str | None = None
    expected_duration: float | None = Field(default=None, gt=0)
    motion: Motion = Motion()
    transition: str = "cut"
    # Optional visual-only cuts inside this scene. Empty preserves the original
    # one-image-per-scene renderer exactly.
    visual_beats: list[VisualBeat] = []
    factual_notes: list[str] = []

    @model_validator(mode="after")
    def valid_visual_beats(self):
        if self.visual_beats:
            starts=[b.start for b in self.visual_beats]
            if starts[0] != 0:
                raise ValueError("visual_beats must start at 0 seconds")
            if starts != sorted(starts) or len(starts) != len(set(starts)):
                raise ValueError("visual_beats starts must be strictly increasing")
            if any(not (b.asset or b.asset_url) for b in self.visual_beats):
                raise ValueError("each visual beat must declare asset or asset_url")
            if self.visual_qa_requirements:
                for index, beat in enumerate(self.visual_beats):
                    if not beat.visual_qa_requirements:
                        raise ValueError(f"visually required scene beat {index} must declare visual_qa_requirements")
                    if not (beat.visual_qa_labels or beat.visual_qa_expected_sha256):
                        raise ValueError(f"visually required scene beat {index} must declare visual_qa_labels or visual_qa_expected_sha256")
        return self
    # Human-readable (any language) QA requirements shown in reports.
    visual_qa_requirements: list[str] = []
    # English zero-shot labels describing what MUST be visible for semantic QA.
    visual_qa_labels: list[str] = []
    # English zero-shot labels describing wrong-domain/incorrect content that must NOT dominate.
    visual_qa_negative_labels: list[str] = []
    # Fallback assets tried in order by the visual-QA recovery loop, most-preferred first.
    recovery_candidates: list[AssetCandidate] = []
    # SHA-256 hashes of previously-vetted, known-correct source asset bytes for this
    # scene (primary asset + any recovery candidates). Deterministic provenance
    # evidence: proves the exact known-good file is in use, independent of any
    # similarity-score judgment. A mismatch (wrong/substituted file) fails closed.
    visual_qa_expected_sha256: list[str] = []
    overlay_title: str | None = None
    # Authored role/text segments for this scene's TTS audio (see
    # shorts_studio/prosody.py). When empty, the engine runs the same
    # automatic Korean boundary planner over the flat `narration` string as
    # a single segment (shorts_studio.prosody.build_auto_plan).
    narration_plan: list[NarrationPhrase] = []

class Project(BaseModel):
    title: str
    width: int = 1080
    height: int = 1920
    fps: int = 30
    overlay_title: str | None = None
    scenes: list[Scene] = Field(min_length=1)
    # Cap on per-scene asset-swap/re-render/re-QA cycles before the whole production FAILs.
    max_visual_recovery_attempts: int = Field(default=2, ge=0)
    # Whole-video source-family diversity gates (global reuse ratio, sliding
    # novelty window, first-5s family coverage, pre-render source budget).
    # Opt-in rather than universal: they assume a real archival photo pool
    # rich enough to avoid revisiting the same evidence across adjacent
    # scenes, which holds for a topic like the Radium Girls but not for a
    # photo-sparse investigation like the Comet crashes, where the same
    # handful of real accident-report photos legitimately gets revisited
    # across narratively adjacent beats. Projects that do have the material
    # (and the narrative complaint these gates were built for) turn this on.
    strict_source_diversity: bool = False

    @model_validator(mode="after")
    def vertical(self):
        if (self.width,self.height)!=(1080,1920):
            raise ValueError("V1 output must be 1080x1920")
        if self.fps < 30:
            raise ValueError("fps must be >=30")
        return self
