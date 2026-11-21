#!/usr/bin/env bash
# Local Blender 5.0.1 and the pinned CC0 car (the cloud container is wiped between sessions). Same pinned hashes as the CI workflows.
# Usage: scripts/episode/setup_blender.sh [dir]   (default /opt/bl)
set -euo pipefail
DIR=${1:-/opt/bl}
mkdir -p "$DIR" && cd "$DIR"
if [ ! -f car.blend ]; then
  curl -fLsS --max-time 120 -o car.blend https://github.com/mingi201209-star/shorts-studio/releases/download/rumble-episode2-scene-a82e0582-20261018/guardrail-car-cc0-pinned-a82e0582.blend
fi
echo "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877  car.blend" | sha256sum -c -
if [ ! -x blender-5.0.1-linux-x64/blender ]; then
  for base in https://download.blender.org/release https://ftp.nluug.nl/pub/graphics/blender/release https://mirror.clarkson.edu/blender/release; do
    if curl -fLsS --max-time 400 "$base/Blender5.0/blender-5.0.1-linux-x64.tar.xz" -o b.tar.xz \
       && echo "8019580ee1b7262e505f4196a00237ccf743c88d205b38d34201510676e60b09  b.tar.xz" | sha256sum -c -; then
      break
    fi
  done
  tar -xJf b.tar.xz && rm b.tar.xz
fi
echo "blender: $DIR/blender-5.0.1-linux-x64/blender   car: $DIR/car.blend"
