"""Full-frame visual continuity audit; not an engineering crash certification."""
import bpy, json, math, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vehicle_geometry import mirror_connections,tyre_objects
from mathutils import Vector
from mathutils.kdtree import KDTree
from bpy_extras.object_utils import world_to_camera_view

s=bpy.context.scene
car=bpy.data.objects['CC0 detailed sedan animated as a rigid car']
rail=next(o for o in s.objects if o.name.startswith('Real 3D W-beam rail'))
out=Path(os.environ['VISUAL_V2_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
parts=[o for o in car.children_recursive if o.type=='MESH']
s.frame_set(1);bpy.context.view_layer.update()
# Parent-relative matrices must stay fixed, including spokes under wheel pivots.
reference={o.name:o.matrix_local.copy() for o in parts}
camera=s.camera.matrix_world.copy()
tyres=tyre_objects(car)
errors=[]; frames=[]
def require(ok,label,frame,value):
 if not ok:errors.append({'frame':frame,'check':label,'value':value})
def meshgap(a,b):
 tree=KDTree(len(b.data.vertices))
 for j,v in enumerate(b.data.vertices):tree.insert(b.matrix_world@v.co,j)
 tree.balance()
 return min(tree.find(a.matrix_world@v.co)[2] for v in a.data.vertices)
keys=rail.data.shape_keys.key_blocks
basis=keys[0]
xs=sorted({round(v.co.x,4) for v in basis.data})
dx=xs[1]-xs[0]
last_pos=None;last_rot=None;last_rail=None;distance=0.
wheels=[o for o in car.children if o.name.startswith('WheelPivot_')]
assert len(wheels)==4,'WHEEL_PIVOTS_MISSING'
window=list(s.get('primary_contact_frames',[]))
assert len(window)==2 and 1<=window[0]<window[1]<=s.frame_end
peak_y=None
for f in range(s.frame_start,s.frame_end+1):
 s.frame_set(f);bpy.context.view_layer.update()
 rigid_error=max(abs(o.matrix_local[i][j]-reference[o.name][i][j]) for o in parts for i in range(4) for j in range(4))
 require(rigid_error<1e-5,'PART_RELATIVE_TRANSFORM',f,rigid_error)
 camera_error=max(abs(s.camera.matrix_world[i][j]-camera[i][j]) for i in range(4) for j in range(4))
 require(camera_error<1e-6,'CAMERA_MOVED',f,camera_error)
 points=[o.matrix_world@Vector(c) for o in parts for c in o.bound_box]
 screen=[world_to_camera_view(s,s.camera,p) for p in points]
 bounds=[min(p.x for p in screen),max(p.x for p in screen),min(p.y for p in screen),max(p.y for p in screen)]
 require(min(p.z for p in screen)>0 and bounds[0]>=.05 and bounds[1]<=.95 and bounds[2]>=.05 and bounds[3]<=.95,'CAR_FRAME_MARGIN',f,bounds)
 gaps=[]
 for a,b,limit in mirror_connections(car):
  mirror_distance=meshgap(bpy.data.objects[a],bpy.data.objects[b])
  gaps.append([a,b,mirror_distance])
  require(mirror_distance<limit,'MIRROR_DETACHED',f,[a,b,mirror_distance])
 tyre_ground=[min((o.matrix_world@v.co).z for v in o.data.vertices)-(-.045) for o in tyres]
 require(all(-.005<=g<=.015 for g in tyre_ground),'TYRE_GROUND',f,tyre_ground)
 # Evaluate actual shape-key weights at this frame, independent of stored contact metadata.
 rv=[v.co.copy() for v in basis.data]
 for key in keys[1:]:
  if abs(key.value)>1e-8:
   for i,v in enumerate(rv):v+=(key.data[i].co-basis.data[i].co)*key.value
 rv=[rail.matrix_world@v for v in rv]
 cols={}
 for p in rv:
  c=cols.setdefault(round(p.x,4),[float('inf'),float('-inf'),float('inf')])
  c[0]=min(c[0],p.y);c[1]=max(c[1],p.z);c[2]=min(c[2],p.z)
 env={};witnesses={}
 for ob in parts:
  m=ob.matrix_world
  for vertex in ob.data.vertices:
   w=m@vertex.co
   index=round((w.x-xs[0])/dx)
   if not 0<=index<len(xs):continue
   k=xs[index];c=cols[k]
   if c[2]-.01<=w.z<=c[1]+.01 and w.y>env.get(k,-9):
    env[k]=w.y;witnesses[k]={'part':ob.name,'car_point_m':[round(v,5) for v in w],'rail_column_x_m':k}
 contact_key=min(env,key=lambda k:cols[k][0]-env[k]) if env else None
 contact_gap=cols[contact_key][0]-env[contact_key] if contact_key is not None else None
 witness=witnesses.get(contact_key)
 require(contact_gap is not None and contact_gap>=-.025,'RAIL_PENETRATION',f,contact_gap)
 if window[0]<=f<=window[1]:
  require(contact_gap is not None and contact_gap<=.03,'CONTACT_LOST',f,contact_gap)
 # Residual deformation may remain after exit; any NEW peak requires contact.
 if peak_y is not None:
  new_peak=max(v.y-y for v,y in zip(rv,peak_y))
  require(new_peak<=.003 or (contact_gap is not None and contact_gap<=.03),'DEFORMATION_WITHOUT_CONTACT',f,new_peak)
 peak_y=[max(v.y,y) for v,y in zip(rv,peak_y)] if peak_y else [v.y for v in rv]
 pos=car.matrix_world.translation.copy();rot=car.matrix_world.to_quaternion()
 step=(pos-last_pos).length if last_pos else 0
 turn=rot.rotation_difference(last_rot).angle if last_rot else 0
 railstep=max((a-b).length for a,b in zip(rv,last_rail)) if last_rail else 0
 distance+=step
 for wheel in wheels:
  expected=distance/(wheel['rolling_radius_local']*car.matrix_world.to_scale().x)
  require(abs(wheel.rotation_euler.x-expected)<.0001,'WHEEL_ROLL_MISMATCH',f,[wheel.name,wheel.rotation_euler.x,expected])
 require(step<=.12,'CAR_POSITION_JUMP',f,step)
 require(turn<=math.radians(3),'CAR_ROTATION_JUMP',f,math.degrees(turn))
 require(railstep<=.12,'RAIL_POSITION_JUMP',f,railstep)
 frames.append({'frame':f,'bounds':[round(v,5) for v in bounds],'contact_witness':witness,'contact_gap_m':None if contact_gap is None else round(contact_gap,5),'tyre_ground_m':[round(g,5) for g in tyre_ground],'car_step_m':round(step,5),'turn_degrees':round(math.degrees(turn),5),'rail_step_m':round(railstep,5),'relative_transform_error':rigid_error})
 last_pos=pos;last_rot=rot;last_rail=rv
for f in range(s.frame_start,s.frame_end):
 s.frame_set(f,subframe=.5)
 weights=[key.value for key in keys[1:]]
 require(abs(sum(weights)-1)<1e-5 and min(weights)>=-1e-6,'SHAPE_KEY_BLEND',f+.5,sum(weights))
from validate_supports import support_errors
support_failures,support_frames=support_errors(s,rail)
errors.extend(support_failures)
report={'support_frames':support_frames,'vehicle_variant':car.get('vehicle_variant','legacy'),'status':'FAIL' if errors else 'PASS','frames_checked':len(frames),'mesh_parts':len(parts),'errors':errors,'frames':frames,'editorial_quality':'UNASSESSED','physical_validation':False}
(out/'motion_validation.json').write_text(json.dumps(report,indent=2))
print('FULL_FRAME_AUDIT',json.dumps({k:v for k,v in report.items() if k not in ('frames','support_frames')}),flush=True)
assert not errors,('MOTION_AUDIT_FAILED',len(errors))
