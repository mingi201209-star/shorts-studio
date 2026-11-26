"""Long-form film 1: "7 clever ways roads stop things that are out of control" (16:9, about six minutes). Nine narration blocks
(examples/longform/lf01-speech-plan.json): an intro, seven chapters, an outro. Every line is shown by a shot of the episode it talks
about (owner rule 2026-11-25: show exactly what each line says); a line that names several things cuts on the word where each
appears. Chapters: EP.13 guardrail end, EP.15 cable barrier, EP.26 rolling barrier, EP.19 spike strip, EP.18 wedge barrier, EP.21
rockfall net, EP.22 runway arrestor bed."""
from __future__ import annotations

from benchmarks.longform import lf_timeline as lt

AUDIO_ROOT = lt.ROOT / "examples/longform/lf01-audio"


def w(word):
    return ("word", word)


BLOCKS = [
    {"id": "lf01_intro", "lines": [
        [("terminal", "A-ribbon", 0)],                                                  # roads catch things out of control
        [("cable", "B-oncoming", 0)],                                                   # a car crossing into oncoming traffic
        [("rocknet", "A1-boulder-in-the-net", 0)],                                      # a twenty-ton boulder
        [("emas", "B-runs-off-the-end", 0)],                                            # a jet that couldn't stop in time
        [("wedge", "A1-slam", 0), ("cable", "A2-slingshot", ("word", "Stopping", 2))],  # stopping is easy / without hurting anyone
        [("terminal", "C-steel-head", 0), ("cable", "C-ropes", 1 / 7), ("roller", "E-rollers-spin", 2 / 7), ("spike", "D-punch-into-tread", 3 / 7),
         ("wedge", "B-rises-in-a-second", 4 / 7), ("rocknet", "E-stretches-twenty-feet", 5 / 7), ("emas", "E-blocks-crush", 6 / 7)],   # seven ways
    ]},
    {"id": "lf01_ch1", "lines": [
        [("terminal", "A-ribbon", 0)],
        [("terminal", "B1-blunt-end", 0)],
        [("terminal", "B2-into-the-cabin", 0)],
        [("terminal", "C-steel-head", 0)],
        [("terminal", "D-inside", 0)],
        [("terminal", "E-slows-the-car", 0)],
        [("terminal", "F-posts-snap", 0)],
        [("terminal", "G-two-car-lengths", 0)],
    ]},
    {"id": "lf01_ch2", "lines": [
        [("cable", "A1-caught", 0)],
        [("cable", "B-oncoming", 0)],
        [("cable", "C-ropes", 0)],
        [("cable", "D-posts-fold", 0)],
        [("cable", "A2-slingshot", 0), ("cable", "E-eight-feet", 0.5)],
        [("cable", "F-gently", 0)],
        [("cable", "G-steers-back", 0)],
        [("cable", "H-steel-net", 0)],
    ]},
    {"id": "lf01_ch3", "lines": [
        [("roller", "A1-pressed-into-rollers", 0)],
        [("roller", "B-korean-curve", 0)],
        [("roller", "C-steel-scrapes", 0)],
        [("roller", "D-foam-on-posts", 0)],
        [("roller", "E-rollers-spin", 0)],
        [("roller", "F-foam-squashes", 0)],
        [("roller", "G-crash-into-rotation", 0)],
        [("roller", "H1-keeps-rolling", 0), ("roller", "H2-back-to-its-lane", w("is"))],
        [("roller", "I-62-mph-test", 0)],
    ]},
    {"id": "lf01_ch4", "lines": [
        [("spike", "A1-quills-punch-in", 0)],
        [("spike", "B-sixty", 0)],
        [("spike", "C1-hollow-tube", 0)],
        [("spike", "D-punch-into-tread", 0)],
        [("spike", "E-snap-off", 0)],
        [("spike", "F-like-a-straw", 0)],
        [("spike", "G-flat-in-half-a-minute", 0)],
        [("spike", "H-slows-straight", 0)],
    ]},
    {"id": "lf01_ch5", "lines": [
        [("wedge", "A1-slam", 0)],
        [("wedge", "B-rises-in-a-second", 0)],
        [("wedge", "C1-pit", 0), ("wedge", "C2-hinge", 0.5)],
        [("wedge", "D-pistons", 0)],
        [("wedge", "E-hits-the-steel", 0)],
        [("wedge", "F-into-the-concrete", 0)],
        [("wedge", "G-back-end-flips", 0)],
        [("wedge", "H-truck", 0)],
    ]},
    {"id": "lf01_ch6", "lines": [
        [("rocknet", "A1-boulder-in-the-net", 0)],
        [("rocknet", "B-nets-above-the-road", 0)],
        [("rocknet", "C-chain-mail-rings", 0)],
        [("rocknet", "D-not-stopped-dead", 0)],
        [("rocknet", "E-stretches-twenty-feet", 0)],
        [("rocknet", "F-brake-rings", 0)],
        [("rocknet", "G-loops-shrink-heat", 0)],
        [("rocknet", "H-nothing-snaps", 0)],
        [("rocknet", "I-twenty-tons-sixty-mph", 0)],
        [("rocknet", "J-replace-the-brakes", 0)],
    ]},
    {"id": "lf01_ch7", "lines": [
        [("emas", "A1-jet-in-the-bed", 0)],
        [("emas", "B-runs-off-the-end", 0)],
        [("emas", "C-crushable-blocks", 0)],
        [("emas", "D-full-of-bubbles", 0)],
        [("emas", "E-blocks-crush", 0)],
        [("emas", "F-tires-sink-in", 0)],
        [("emas", "G-every-block", 0)],
        [("emas", "H-eighty-mph", 0)],
        [("emas", "I-two-dozen-planes", 0)],
        [("emas", "J-replace-blocks", 0)],
    ]},
    {"id": "lf01_outro", "lines": [
        [("terminal", "H-waiting", 0)],                                                 # did you spot the trick
        [("cable", "B-oncoming", 0), ("wedge", "G-back-end-flips", w("It"))],           # speed / the speed disappears too fast
        [("cable", "E-eight-feet", 0)],                                                 # stretch the stop out
        [("terminal", "D-inside", 0), ("cable", "A2-slingshot", w("cables")), ("rocknet", "E-stretches-twenty-feet", w("nets")),
         ("emas", "E-blocks-crush", w("and"))],                                         # steel / cables / nets / blocks
        [("rocknet", "D-not-stopped-dead", 0)],                                         # the longer the stop
        [("roller", "B-korean-curve", 0)],                                              # the engineering you pass every day
    ]},
]

# per (episode, row) camera adjustments for 16:9 found in the storyboard review
OVERRIDES: dict = {
    ("wedge", "B-rises-in-a-second"): {                                            # the rising plate was below the 16:9 frame
        "cam_a": {"rel": "world", "loc": (-0.4, 6.5, 1.5), "target": (-1.9, -1.0, 0.15), "lens": 24.0, "fstop": 5.6},
        "cam_b": {"rel": "world", "loc": (-0.5, 6.0, 1.4), "target": (-1.9, -1.0, 0.25), "lens": 24.0, "fstop": 5.6}},
}

TITLE = "7 Clever Ways Roads Stop Things That Are Out of Control"
CHAPTER_NAMES = {"lf01_intro": "Intro", "lf01_ch1": "1. The guardrail end that peels into a ribbon", "lf01_ch2": "2. Cable barriers",
                 "lf01_ch3": "3. The guardrail that spins", "lf01_ch4": "4. Police spike strips", "lf01_ch5": "5. The wedge barrier",
                 "lf01_ch6": "6. Rockfall nets", "lf01_ch7": "7. Runways built to crumble", "lf01_outro": "The trick they all share"}


def layout() -> dict:
    return lt.build_layout(BLOCKS, AUDIO_ROOT)


def episode_timeline(key: str, lay: dict | None = None):
    return lt.layout_episode_timeline(lay or layout(), key, OVERRIDES)


if __name__ == "__main__":
    import json
    lay = layout()
    print(json.dumps({"seconds": lay["seconds"], "frames": lay["frames"], "shots": len(lay["shots"]),
                      "per_episode": {k: sum(s["frames"] for s in v) for k, v in lay["episodes"].items()}}, indent=1))
