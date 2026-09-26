from pydantic import BaseModel, ConfigDict, Field, model_validator

from .retention_rules import HOOK_TYPES

# A manifest field the engine doesn't recognize -- a typo (hok_type), a
# field name left over from a design that changed, or one borrowed from a
# different branch's schema -- must fail loudly, not vanish silently. This
# is not a hypothetical: examples/train_wheels.json (PR #24) shipped with a
# real hook_type declaration that a pre-retention-engine build of these
# models silently dropped (pydantic's own default is extra="ignore"),
# reporting `validate` PASS the entire time. Verified before enabling this
# repo-wide (Phase 0 of the retention-foundation integration): every field
# actually present in comet.json, radium_girls.json, titanic_fourth_funnel.json,
# and train_wheels.json is modeled below -- forbidding extra fields does not
# reject any of them (see tests/test_unknown_field_fail_closed.py).
_FORBID_EXTRA = ConfigDict(extra="forbid")

class Motion(BaseModel):
    model_config = _FORBID_EXTRA
    type: str = "push_in"

class AssetCandidate(BaseModel):
    """A fallback asset the visual-QA recovery loop may swap in for a scene."""
    model_config = _FORBID_EXTRA
    asset: str | None = None
    asset_url: str | None = None
    attribution: str | None = None

class VisualBeat(BaseModel):
    """An optional timed visual cut inside one narration scene."""
    model_config = _FORBID_EXTRA
    start: float = Field(ge=0)
    asset: str | None = None
    asset_url: str | None = None
    attribution: str | None = None
    motion: Motion = Motion()
    visual_qa_requirements: list[str] = Field(default_factory=list)
    visual_qa_labels: list[str] = Field(default_factory=list)
    visual_qa_negative_labels: list[str] = Field(default_factory=list)
    visual_qa_expected_sha256: list[str] = Field(default_factory=list)
    # Optional, free-text label for what NEW information this beat delivers
    # (e.g. "storage_tank_scale", "rupture_point", "trial_outcome"). Purely
    # authorial -- the engine does not interpret its meaning, only whether
    # the exact same label appears more than once (see
    # final_video_qa.compute_information_progression). A beat with no
    # info_role is simply not checked; this keeps every manifest that
    # predates the Information Change Contract unaffected.
    info_role: str | None = None

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
    model_config = _FORBID_EXTRA
    role: str  # HOOK|SETUP|CRISIS|INVESTIGATION|REVEAL|EXPLANATION|PAYOFF
    text: str = Field(min_length=1)
    focus: bool = False  # the emphasis/result target, e.g. a REVEAL's delivered payload
    pace: str | None = None  # optional explicit Edge TTS rate override, e.g. "+2%"
    # Which retention mechanism a HOOK-role phrase is CLAIMING to use (see
    # retention_rules.HOOK_TYPES). This is author-declared structural
    # metadata, not a semantic verification: valid_hook_type below only
    # checks the value is one of the known HOOK_TYPES enum members, and
    # final_video_qa.verify_hook_opener only checks that the value is set
    # AND that the phrase's text contains SOME tension marker (any of them,
    # from retention_rules.has_tension_marker) -- it never confirms the
    # declared type is the marker that actually fired. A phrase can declare
    # hook_type="contradiction" while its text contains only a danger word
    # and no contradiction at all, and this passes today (demonstrated with
    # a real adversarial fixture in the Phase 0 report). Fixing this
    # requires reading comprehension a regex/enum check cannot provide;
    # it is an explicit known limitation of this deterministic layer, left
    # to the planned Psychological Entertainment Contract's semantic
    # Observed-Evidence layer, not something to approximate here with more
    # keyword lists.
    hook_type: str | None = None

    @model_validator(mode="after")
    def valid_hook_type(self):
        if self.hook_type is not None and self.hook_type not in HOOK_TYPES:
            raise ValueError(f"hook_type must be one of {HOOK_TYPES}, got {self.hook_type!r}")
        return self

class Scene(BaseModel):
    model_config = _FORBID_EXTRA
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
    model_config = _FORBID_EXTRA
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
    # Opt-in retention-engine contract: First-Second Hook, Information
    # Change, Story Progression, Ending Payoff, First-10s Retention, and
    # Runtime Discipline (see shorts_studio/final_video_qa.py and
    # shorts_studio/idea_gate.py). Off by default so every manifest written
    # before this contract existed (comet.json, radium_girls.json,
    # titanic_fourth_funnel.json) keeps passing QA exactly as before -- this
    # is a stricter bar a NEW production opts into, not a retroactive
    # requirement.
    #
    # "Runtime Discipline" is the category name; what it actually checks
    # today (final_video_qa.verify_no_redundant_narration, reported under
    # the "no_redundant_narration" key) is near-duplicate-sentence
    # detection ONLY -- there is no total-video-length gate anywhere in this
    # engine under this name or any other. Do not read "Runtime Discipline
    # PASS" as "this video is an appropriate length."
    #
    # strict_retention_contract PASS is a structural/deterministic filter,
    # not a human-interest or entertainment-value verification: every check
    # in this contract trusts author-declared metadata (a role label, a
    # hook_type, an info_role string) rather than confirming it against the
    # real narration/visual content. See shorts_studio/final_video_qa.py's
    # retention-engine module docstring and the Phase 0 report for
    # concretely demonstrated cases where this contract PASSes content a
    # human would call boring or mislabeled. Never report a
    # strict_retention_contract PASS as proof a video is entertaining, or
    # as "fun verified" -- only real post-publish data, or a human review,
    # can establish that.
    strict_retention_contract: bool = False

    @model_validator(mode="after")
    def vertical(self):
        if (self.width,self.height)!=(1080,1920):
            raise ValueError("V1 output must be 1080x1920")
        if self.fps < 30:
            raise ValueError("fps must be >=30")
        return self
