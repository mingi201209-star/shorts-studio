# Visual Production Engine V2 — evidence-led production contract

This is a production contract, not an "entertainment score". It exists because
the current renderer can satisfy script/retention/semantic QA while still
converging to a visually repetitive teaching-slide style.

## External evidence used

- YouTube says Shorts ranking uses whether viewers choose to watch, average
  view duration, average percentage viewed, and satisfaction signals.
- YouTube's own Shorts creator guidance emphasizes the opening instant and
  maintaining momentum / renewed curiosity after the hook.
- YouTube creator guidance also recommends visually appealing moments and
  captions for viewers who watch without sound.
- Multimedia-learning evidence repeatedly warns that redundant on-screen
  prose can compete with the visual explanation. Short labels/signals can be
  useful, but the picture should carry the mechanism whenever possible.
- Audio is a production-quality layer, not an assumed ranking hack. Platform
  guidance supports sound-aware editing, but this repo must not claim music or
  SFX automatically improve organic ranking.

## V2 machine contract

For an opt-in production (strict_production_quality_v2=true):

1. Opening beat is real motion or physical animation backed by moving media.
2. No explanatory-card beat appears in the first five seconds.
3. Two explanatory cards may not appear consecutively.
4. Sentence-level prose inside the picture area is rejected. Use no internal
   text or short labels; spoken captions remain separate.
5. A second moving hero visual must appear in the 10–25 second window.
6. The final visual must resolve on real motion or physical animation.
7. At least 65% of the final duration must be real-world imagery or
   physical-state visuals rather than explanatory cards.
8. At least 20% must remain real-world visual evidence.
9. Reusing a long real clip is allowed only when a later beat starts at a
   genuinely different source moment (source_start); crop/zoom of the same
   still is not considered a state change.

The numeric ratios are repo production baselines, not claims about a
YouTube algorithm threshold.

## Human gate that cannot be automated honestly

After machine QA passes, the render is still not automatically upload-ready.
A human must answer:

> 소리 없이 봐도 10초 이상 계속 보고 싶은가?

If the answer is NO, the production is not an upload candidate even when every
machine check passes.

## Art direction

- Real phenomenon / evidence is the protagonist.
- Diagrams are temporary explanatory tools, not the default visual language.
- Black outer canvas and stable caption-safe composition remain.
- Avoid repeated white cards, title bars, paragraph text, decorative chrome,
  and arbitrary motion.
- Motion must show a changing physical state, a new piece of evidence, or a
  genuinely different semantic moment.
- The middle of the Short must not look cheaper or more static than the hook.
- End on the most satisfying visual result, not on a summary slide.
