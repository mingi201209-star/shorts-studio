import bpy,json,math,os
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
from bpy_extras.object_utils import world_to_camera_view
d=Path(os.environ.get('VISUAL_V2_OUTPUT','/tmp/guardrail_v2_out'))
scene=bpy.context.scene
cam=scene.camera
assert cam is not None and cam.type=='CAMERA'
rail=next(o for o in scene.objects if o.name.startswith('Real 3D W-beam rail'))
guide=scene.objects.get('UNDISTORTED_REFERENCE_RAIL_CONTOUR_CYAN')
car=scene.objects.get('CC0 detailed sedan animated as a rigid car')
assert guide is not None and car is not None
assert scene.render.resolution_x==1080 and scene.render.resolution_y==1920
assert scene.render.resolution_percentage==100
assert not cam.animation_data and cam.parent is None
assert scene.cycles.use_denoising
width=1080;height=1920
keys=rail.data.shape_keys.key_blocks
basis=keys[0]
NV=len(basis.data)
def rail_world(frame):
 """Exact relative shape-key blend of every rail vertex at a frame."""
 scene.frame_set(frame)
 co=[basis.data[i].co.copy() for i in range(NV)]
 for kb in keys[1:]:
  if kb.value:
   for i in range(NV):
    co[i]+=(kb.data[i].co-basis.data[i].co)*kb.value
 return [rail.matrix_world@c for c in co]
def screen(p):
 v=world_to_camera_view(scene,cam,p)
 return {'x':round(float(v.x)*width,2),'y':round((1-float(v.y))*height,2),'depth':round(float(v.z),3)}
base=rail_world(1)
peak=rail_world(40)
idx=max(range(NV),key=lambda i:(peak[i]-base[i]).length)
screen_base=screen(base[idx]);screen_peak=screen(peak[idx])
delta=math.hypot(screen_base['x']-screen_peak['x'],screen_base['y']-screen_peak['y'])
world_deflection=round((peak[idx]-base[idx]).length,3)
# Car visibility uses all child-mesh bounds, not only the car origin.
car_meshes=[c for c in car.children_recursive if c.type=='MESH']
# Exact detached-piece regression: neither side mirror may float away.
def mesh_gap(a,b):
 pts=[b.matrix_world@v.co for v in b.data.vertices]
 t=KDTree(len(pts))
 for j,pt in enumerate(pts):t.insert(pt,j)
 t.balance()
 return min(t.find(a.matrix_world@v.co)[2] for v in a.data.vertices)
mirror_gaps={}
for fr in (1,22,40,45):
 scene.frame_set(fr)
 bpy.context.view_layer.update()
 for side in ('','.001'):
  arm=bpy.data.objects['Mirror arm'+side]
  shell=bpy.data.objects['Mirror shell'+side]
  body=bpy.data.objects['Cab and roof']
  aa=mesh_gap(arm,body);ss=mesh_gap(shell,arm)
  mirror_gaps[str(fr)+':'+(side or 'left')]=[round(aa,4),round(ss,4)]
  assert aa<.025 and ss<.02,('DETACHED_MIRROR_PIECES',fr,side,aa,ss)
print('MIRROR_ATTACHMENT_QA_PASS',mirror_gaps,flush=True)
car_bounds={};contact={}
xs=sorted({round(p.x,4) for p in base})
for fr in (1,22,40):
 rw=rail_world(fr)
 bpy.context.view_layer.update()
 points=[]
 for child in car_meshes:
  for corner in child.bound_box:
   v=world_to_camera_view(scene,cam,child.matrix_world@Vector(corner))
   if v.z>0:
    points.append((float(v.x),float(v.y)))
 assert points,('CAR_NOT_VISIBLE',fr)
 b=[round(min(x for x,y in points),4),round(max(x for x,y in points),4),round(min(y for x,y in points),4),round(max(y for x,y in points),4)]
 car_bounds[str(fr)]=b
 assert b[0]>=.05 and b[2]>=.05,('CAR_CLIPS_LEFT_OR_BOTTOM',fr,b)
 assert b[1]<=.95 and b[3]<=.95,('CAR_CLIPS_RIGHT_OR_TOP',fr,b)
 # Car/rail contact gap per rail column: rail face (min y of the deformed
 # column) minus the car body's max y inside that column's height band.
 col={}
 for p in rw:
  k=round(p.x,4)
  c=col.setdefault(k,[9.,-9.,9.])
  c[0]=min(c[0],p.y);c[1]=max(c[1],p.z);c[2]=min(c[2],p.z)
 dx=(xs[-1]-xs[0])/(len(xs)-1)
 env={}
 for child in car_meshes:
  m=child.matrix_world
  for v in child.data.vertices:
   w=m@v.co
   k=xs[min(max(int(round((w.x-xs[0])/dx)),0),len(xs)-1)]
   c=col[k]
   if c[2]-.01<=w.z<=c[1]+.01 and w.y>env.get(k,-9.):env[k]=w.y
 gaps=[col[k][0]-y for k,y in env.items()]
 contact[str(fr)]=round(min(gaps),4) if gaps else None
assert contact['1'] is not None and contact['1']>.10,('NO_VISIBLE_APPROACH_GAP',contact)
for fr in ('22','40'):
 assert contact[fr] is not None and -.025<=contact[fr]<=.03,('CAR_RAIL_NOT_IN_CONTACT_OR_PENETRATING',fr,contact)
scene.frame_set(1)
out={'scene':'Guardrail V3 contact-solved isolated development','quality_gate':'UNASSESSED','camera_static':True,'native_resolution':[width,height],'samples':scene.cycles.samples,'frame1':screen_base,'frame40':screen_peak,'projected_delta_px':round(delta,2),'world_deflection_m':world_deflection,'rail_vertex_index':idx,'car_bbox_normalized':car_bounds,'car_rail_contact_gap_m':contact,'mirror_attachment_gaps_m':mirror_gaps,'has_reference_guide':bool(guide),'editorial_flag':'CONCEPTUAL animation, NOT crash-test validated'}
d.joinpath('v2_validation.json').write_text(json.dumps(out,indent=2))
print('RENDER_QA_REPORT',json.dumps(out),flush=True)
assert delta>=40,'insufficient visible rail displacement'
assert world_deflection>=.35,'rail deflection understated'
assert scene.cycles.samples>=16
assert screen_base['depth']>0 and screen_peak['depth']>0
assert 20<=screen_peak['x']<=1060 and 100<=screen_peak['y']<=1810,(screen_peak,delta)
print('V2_SCENE_GEOMETRY_QA_PASS',flush=True)
