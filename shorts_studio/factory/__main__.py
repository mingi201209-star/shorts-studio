"""Read-only CLI for inspecting topic work before expensive 3D work."""
import argparse
import json

from .contracts import FactoryManifest, TemplateRegistry
from .planner import create_plan
from .series import SeriesScope, require_topic_in_series


def main() -> None:
    parser = argparse.ArgumentParser(description="Native 3D Shorts planning and QA gating")
    parser.add_argument("manifest")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--series", required=True, help="locked first-season topic list")
    parser.add_argument("--cache-dir", default=".factory-cache")
    args = parser.parse_args()
    manifest = FactoryManifest.load(args.manifest)
    require_topic_in_series(manifest, SeriesScope.load(args.series))
    result = create_plan(manifest,
                         TemplateRegistry.load(args.registry), args.cache_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["ready_to_render"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
