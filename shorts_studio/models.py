from pydantic import BaseModel, Field, model_validator

class Motion(BaseModel):
    type: str = "push_in"

class AssetCandidate(BaseModel):
    """A fallback asset the visual-QA recovery loop may swap in for a scene."""
    asset: str | None = None
    asset_url: str | None = None
    attribution: str | None = None

class NarrationPhrase(BaseModel):
    """One unit of the Korean Prosody Planner's structured representation
    (see shorts_studio/prosody.py). A scene's spoken delivery is built from
    an ordered list of these rather than one flat narration string synthesized
    sentence-by-sentence with identical pauses everywhere."""
    role: str  # HOOK|SETUP|CRISIS|INVESTIGATION|REVEAL|EXPLANATION|PAYOFF
    text: str = Field(min_length=1)
    # what kind of break follows THIS phrase: continuation|weak|medium|strong|anticipatory|terminal
    boundary: str = "terminal"
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
    factual_notes: list[str] = []
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
    # Structured, narrative-role-aware delivery plan for this scene's TTS
    # audio (see shorts_studio/prosody.py). When empty, the engine falls
    # back to auto-splitting `narration` into per-sentence terminal-boundary
    # phrases (the previous, uniform-pause behavior).
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

    @model_validator(mode="after")
    def vertical(self):
        if (self.width,self.height)!=(1080,1920):
            raise ValueError("V1 output must be 1080x1920")
        if self.fps < 30:
            raise ValueError("fps must be >=30")
        return self
