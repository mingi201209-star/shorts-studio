#!/usr/bin/env python3
"""Run 3 equal low-res guardrail frames, then one native-resolution quality/cost sample."""
import bpy, json, os, time, hashlib
from pathlib import Path

out=Path(os.environ["BLENDER_BENCH_OUT"])
out.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.device='CPU'
scene.render.resolution_x=1080
scene.render.resolution_y=1920
scene.render.threads_mode='FIXED'
scene.render.threads=4
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGBA'
scene.cycles.use_denoising=True
data={'machine':'github-hosted ubuntu-24.04 x64 GitHub Actions CPU','blender':bpy.app.version_string,
      'note':'Same authored scene and CC0 asset as phone; Blender package version and CPU architecture may differ. Not production certification.',
      'frames':[]}
for frame,res,samples in [(1,38,8),(35,38,8),(90,38,8),(42,100,16)]:
    scene.frame_set(frame)
    scene.render.resolution_percentage=res
    scene.cycles.samples=samples
    name=f'bench_frame_{frame:04d}_{res}pct_{samples}s.png'
    path=out/name
    scene.render.filepath=str(path)
    start=time.perf_counter()
    bpy.ops.render.render(write_still=True)
    elapsed=round(time.perf_counter()-start,3)
    if not path.is_file() or path.stat().st_size<10000:
        raise RuntimeError(f'Missing/empty frame: {path}')
    row={'frame':frame,'resolution_pct':res,'samples':samples,'seconds':elapsed,
         'file':name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    data['frames'].append(row)
    (out/'benchmark.json').write_text(json.dumps(data,indent=2))
    print('BENCHMARK_RESULT',json.dumps(row),flush=True)
print('BENCHMARK_COMPLETE',len(data['frames']),flush=True)
