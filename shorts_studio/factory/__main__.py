"""Read-only CLI for inspecting topic work before expensive 3D work."""
import argparse
import json

from .contracts import FactoryManifest, TemplateRegistry
from .planner import create_plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Native 3D Shorts planning and QA gating")
    parser.add_argument("manifest")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--cache-dir", default=".factory-cache")
    args = parser.parse_args()
    result = create_plan(FactoryManifest.load(args.manifest),
                         TemplateRegistry.load(args.registry), args.cache_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["ready_to_render"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
