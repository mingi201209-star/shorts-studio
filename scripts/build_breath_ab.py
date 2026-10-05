#!/usr/bin/env python3
"""Derive the A/B subtle-breath comparison manifests from the real
hydroplaning production manifest.

Run AFTER scripts/build_hydroplaning_states.py has already produced
examples/hydroplaning.json and assets/hydroplaning/* (same visual assets,
same narration text, same beat timing) -- this script never regenerates or
modifies any of that. It writes two new manifests that reference the exact
same asset files and differ in exactly one field:

  examples/hydroplaning_breath_a.json  enable_subtle_breaths: false (baseline)
  examples/hydroplaning_breath_b.json  enable_subtle_breaths: true  (subtle breath)

so a real render of each is a true A/B comparison of the TTS layer only --
the visual track, narration text, and every existing QA gate configuration
are byte-for-byte identical between the two manifests. This script is only
used by the exp/tts-subtle-breathing experiment; it must never be referenced
by hydroplaning-render.yml or any other production workflow.
"""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    source = Path("examples/hydroplaning.json")
    if not source.is_file():
        raise RuntimeError(
            "examples/hydroplaning.json not found -- run "
            "scripts/build_hydroplaning_states.py first"
        )
    manifest = json.loads(source.read_text(encoding="utf-8"))

    manifest_a = dict(manifest)
    manifest_a["enable_subtle_breaths"] = False
    manifest_a["title"] = manifest["title"] + " (A: baseline)"
    path_a = Path("examples/hydroplaning_breath_a.json")
    path_a.write_text(json.dumps(manifest_a, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BREATH_AB_MANIFEST_A_READY={path_a}")

    manifest_b = dict(manifest)
    manifest_b["enable_subtle_breaths"] = True
    manifest_b["title"] = manifest["title"] + " (B: subtle breath)"
    path_b = Path("examples/hydroplaning_breath_b.json")
    path_b.write_text(json.dumps(manifest_b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BREATH_AB_MANIFEST_B_READY={path_b}")


if __name__ == "__main__":
    main()
