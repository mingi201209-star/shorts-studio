#!/usr/bin/env python3
"""Derive true production A/B manifests for TTS continuity.

Run after scripts/build_hydroplaning_states.py.  The two manifests have the
same narration, visuals, title, QA contracts and source assets; they differ
only in Project.tts_continuity_mode.  Procedural breaths are explicitly off
in both arms so this experiment isolates provider continuity.
"""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    source = Path("examples/hydroplaning.json")
    if not source.is_file():
        raise RuntimeError(
            "examples/hydroplaning.json missing; run build_hydroplaning_states.py first"
        )
    manifest = json.loads(source.read_text(encoding="utf-8"))

    a = dict(manifest)
    a["enable_subtle_breaths"] = False
    a["tts_continuity_mode"] = "unitized"

    b = dict(manifest)
    b["enable_subtle_breaths"] = False
    b["tts_continuity_mode"] = "scene_continuous"

    out_a = Path("examples/hydroplaning_tts_unitized.json")
    out_b = Path("examples/hydroplaning_tts_continuous.json")
    out_a.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    out_b.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")

    # Fail closed: make sure this is a single-variable experiment.
    aa = json.loads(out_a.read_text(encoding="utf-8"))
    bb = json.loads(out_b.read_text(encoding="utf-8"))
    assert aa.pop("tts_continuity_mode") == "unitized"
    assert bb.pop("tts_continuity_mode") == "scene_continuous"
    assert aa == bb, "A/B manifests drifted in fields other than TTS continuity"

    print(f"TTS_CONTINUITY_A_READY={out_a}")
    print(f"TTS_CONTINUITY_B_READY={out_b}")


if __name__ == "__main__":
    main()
