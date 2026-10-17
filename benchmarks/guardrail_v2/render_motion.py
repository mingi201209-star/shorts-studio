"""Render a contiguous range; frame PNGs are resumable only within this exact build."""
import bpy,os
from pathlib import Path
s=bpy.context.scene
out=Path(os.environ['VISUAL_V2_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
start=int(os.environ.get('PROOF_START','1'));end=int(os.environ.get('PROOF_END','90'))
assert 1<=start<=end<=90
preview=os.environ.get('MOTION_PREVIEW','0')=='1'
s.render.resolution_percentage=20 if preview else 100
s.cycles.samples=2 if preview else 32
s.cycles.use_denoising=True
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB'
for f in range(start,end+1):
 s.frame_set(f);s.render.filepath=str(out/f'frame_{f:04d}.png')
 bpy.ops.render.render(write_still=True)
print('CONTIGUOUS_RENDER_DONE',start,end,'preview',preview,flush=True)
