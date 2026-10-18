"""Inject real Blender defects and require the motion audit to reject each."""
import bpy,os,json,runpy
from pathlib import Path
source=bpy.data.filepath
root=Path(os.environ['VISUAL_V2_OUTPUT'])
audit=Path(__file__).with_name('validate_motion.py')
cases=[('detached_mirror','MIRROR_DETACHED'),('missing_contact','CONTACT_LOST'),('detached_splice_bolt','SUPPORT_BOLT_DETACHED')]
if bpy.data.objects.get('SprungBody_contact_response'):
 cases.extend([('frozen_body','BODY_RESPONSE_ABSENT'),('thick_wheelhouse','WHEEL_ARCH_INTERSECTION')])
for case,expected in cases:
 bpy.ops.wm.open_mainfile(filepath=source)
 s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
 if case=='detached_mirror':
  car=bpy.data.objects['CC0 detailed sedan animated as a rigid car']
  connections=json.loads(car['mirror_connections_json'])
  ob=bpy.data.objects[connections[0][0]]
  ob.location.x+=.5
 elif case=='thick_wheelhouse':
  from vehicle_geometry import tyre_objects
  from mathutils import Vector
  car=bpy.data.objects['CC0 detailed sedan animated as a rigid car']
  arch=bpy.data.objects['Wheelhouse inner liner']
  tyre=min(tyre_objects(car),key=lambda t:(t.matrix_world.translation-arch.matrix_world.translation).length)
  inv=car.matrix_world.inverted();m=inv@arch.matrix_world;back=m.inverted()
  centre=sum((inv@tyre.matrix_world@Vector(v) for v in tyre.bound_box),Vector())/8
  outer=arch['preserved_outer_radius_m'];inner=arch['source_inner_radius_m']
  for vertex in arch.data.vertices:
   p=m@vertex.co;r=((p.y-centre.y)**2+(p.z-centre.z)**2)**.5
   restored=outer-(outer-inner)*(outer-r)/.012
   p.y=centre.y+(p.y-centre.y)*restored/r;p.z=centre.z+(p.z-centre.z)*restored/r
   vertex.co=back@p
 elif case=='frozen_body':
  body=bpy.data.objects['SprungBody_contact_response'];body.animation_data_clear()
  body.rotation_euler=(0,0,0);body.location.z=.45
 elif case=='detached_splice_bolt':
  bolt=next(o for o in s.objects if o.name.startswith('W-beam splice bolt head'))
  for vertex in bolt.data.vertices:vertex.co.z+=.15
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
