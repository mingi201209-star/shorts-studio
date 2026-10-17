"""Inject real Blender defects and require the motion audit to reject each."""
import bpy,os,json,runpy
from pathlib import Path
source=bpy.data.filepath
root=Path(os.environ['VISUAL_V2_OUTPUT'])
audit=Path(__file__).with_name('validate_motion.py')
cases=[('detached_mirror','MIRROR_DETACHED'),('missing_contact','CONTACT_LOST')]
for case,expected in cases:
 bpy.ops.wm.open_mainfile(filepath=source)
 s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
 if case=='detached_mirror':
  ob=bpy.data.objects['Mirror shell']
  ob.location.x+=.5
 else:
  rail=next(o for o in s.objects if o.name.startswith('Real 3D W-beam rail'))
  rail.location.y+=.2
 target=root/'negative'/case;target.mkdir(parents=True,exist_ok=True)
 os.environ['VISUAL_V2_OUTPUT']=str(target)
 try:runpy.run_path(str(audit),run_name='__main__')
 except AssertionError:pass
 else:raise AssertionError(('MUTATION_NOT_REJECTED',case))
 report=json.loads((target/'motion_validation.json').read_text())
 assert any(e['check']==expected for e in report['errors']),(case,report['errors'])
 print('NEGATIVE_REGRESSION_PASS',case,expected,flush=True)
os.environ['VISUAL_V2_OUTPUT']=str(root)
bpy.ops.wm.open_mainfile(filepath=source)
