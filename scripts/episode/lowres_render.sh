#!/usr/bin/env bash
# The whole film at low resolution in parallel shards, for the local gate run before CI (about 15-20 min for ~800 frames).
# Usage, from the repo root: scripts/episode/lowres_render.sh benchmarks/<ep>/render_<x>_3d.py FRAME_COUNT OUT_DIR [SHARDS]
# Then: PYTHONPATH=$PWD python3 benchmarks/<ep>/assemble_<x>_film.py --panels OUT_DIR --frames-dir OUT_DIR/composed --out OUT_DIR/final
set -uo pipefail
R=$1; N=$2; O=$3; K=${4:-4}
BL=${BLENDER:-/opt/bl/blender-5.0.1-linux-x64/blender}
CAR=${CAR:-/opt/bl/car.blend}
mkdir -p "$O"
step=$(( (N + K - 1) / K ))
for ((s=0; s<N; s+=step)); do
  e=$((s + step - 1)); [ "$e" -ge "$N" ] && e=$((N - 1))
  mkdir -p "$O/sh$s"
  "$BL" -b -t 1 --python-exit-code 1 -P "$R" -- --source "$CAR" --frames "$s-$e" --res-scale 0.15 --samples 3 --out "$O/sh$s" > "$O/sh$s.log" 2>&1 &
done
wait
bad=0
for f in "$O"/sh*.log; do
  if grep -q Traceback "$f"; then echo "FAILED: $f"; grep -A8 Traceback "$f" | head -20; bad=1; fi
done
echo "done: $O (failures: $bad)"
exit $bad
