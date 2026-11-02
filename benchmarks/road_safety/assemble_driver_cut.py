"""GitHub-only assembly entry point for narration-matched driver cuts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from benchmarks.road_safety.curious_mechanics_progressive_delivery import assemble


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("driver cut encoding is restricted to GitHub Actions")
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--driver", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variant", choices=list("ABC"), required=True)
    args = parser.parse_args()
    assemble(args.native, args.source, args.variant, args.out, args.driver)


if __name__ == "__main__":
    main()
