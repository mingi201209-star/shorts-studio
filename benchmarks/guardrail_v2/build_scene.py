#!/usr/bin/env python3
"""Premium look-development proof. Conceptual guardrail mechanics, not crash simulation.
Requires Blender 5.0+, Cycles CPU. Assets and geometry created procedurally.
"""
import bpy, math, sys, os
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from pathlib import Path

OUT=Path(os.environ.get('VISUAL_V2_OUTPUT', '/tmp/guardrail_v2_out'))
OUT.mkdir(parents=True,exist_ok=True)
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
mode=args[0] if args else 'still'
res=int(args[1]) if len(args)>1 else 40
samples=int(args[2]) if len(args)>2 else 12

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.device='CPU'
scene.cycles.samples=16
scene.cycles.use_denoising=True
scene.render.resolution_x=1080
scene.render.resolution_y=1920
scene.render.resolution_percentage=100
scene.render.film_transparent=False
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGBA'
scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.camera=None
scene.frame_start=1
scene.frame_end=90
scene.render.fps=30
scene.render.threads_mode='FIXED'
scene.render.threads=4
scene.world.color=(.1,.12,.16)

def mat(name,color,metallic=0,rough=.5,noise_scale=0,bump=.07):
 m=bpy.data.materials.new(name)
 m.diffuse_color=(*color,1)
 m.use_nodes=True
 nodes=m.node_tree.nodes; links=m.node_tree.links
 p=nodes.get('Principled BSDF')
 p.inputs['Base Color'].default_value=(*color,1)
 p.inputs['Metallic'].default_value=metallic
 p.inputs['Roughness'].default_value=rough
 if noise_scale:
  n=nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=noise_scale
  tc=nodes.new('ShaderNodeTexCoord');links.new(tc.outputs['Object'],n.inputs['Vector'])
  n.inputs['Scale'].default_value=noise_scale/40
  n.inputs['Detail'].default_value=3
  b=nodes.new('ShaderNodeBump')
  b.inputs['Strength'].default_value=.20
  b.inputs['Distance'].default_value=bump
  links.new(n.outputs['Fac'],b.inputs['Height'])
  links.new(b.outputs['Normal'],p.inputs['Normal'])
 return m
metal=mat('ZINC - galvanized W-beam steel',(0.50,.53,.54),.80,.36)
postmat=mat('Posts - hot dipped galvanized steel',(.29,.33,.35),.83,.37,140,.012)
darkmetal=mat('Black underbody metal',(.11,.14,.17),.7,.26)
paint=mat('Blue teal metallic car paint',(.028,.28,.35),.67,.21)
glass=mat('Tinted glass',(.055,.13,.17),.6,.14)
rubber=mat('Soft black tire rubber',(.013,.016,.018),.02,.86,38,.02)
road=mat('Fine gritty black asphalt',(.075,.075,.070),.0,.94,240,.025)
shoulder=mat('Dry rocky soil',(.24,.19,.125),0,.96,170,.04)
grass=mat('Muted roadside vegetation',(.12,.17,.07),0,.95,115,.05)
white=mat('Off-white lane marking',(.75,.75,.65),0,.76,80,.015)
rim=mat('Machined aluminum wheels',(.52,.54,.54),.88,.27,82,.004)
orange=mat('Amber lamp reflectors',(.95,.39,.07),.2,.30)
red=mat('Rear brake lamp',(.75,.04,.025),.1,.27)

def box(name,loc,scale,material,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
 obj=bpy.context.object;obj.name=name
 obj.dimensions=scale
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  be=obj.modifiers.new('Rounded machined corners','BEVEL')
  be.width=bevel;be.segments=3
  obj.modifiers.new('Hardened corner normals','WEIGHTED_NORMAL')
 obj.data.materials.append(material)
 return obj

def cylinder(name,loc,radius,depth,material,rotate=(0,0,0),verts=40):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=radius,depth=depth,location=loc,rotation=rotate)
 ob=bpy.context.object;ob.name=name;ob.data.materials.append(material)
 mod=ob.modifiers.new('Soft edge','BEVEL');mod.width=.025;mod.segments=2
 ob.modifiers.new('Normals','WEIGHTED_NORMAL')
 return ob

def point(obj,xyz):
 direction=Vector(xyz)-obj.location
 obj.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()

# Road surface and shoulder -- separated so the two top faces never z-fight.
GROUND=-.045
box('dark fine-grain asphalt roadway',(0,-30.9,-.18),(240,60.9,.27),road,.035)
box('gritty soil shoulder',(0,1.37,-.23),(240,3.6,.37),shoulder,.055)
box('green grass at back',(0,30.7,-.22),(240,55.2,.35),grass,.05)
box('white road edge marking',(0,-.62,-.027),(240,.12,.006),white,.004)
for i in range(-117,118,3):
 box('intermittent dashed line', (i,-3.66,-.021),(1.6,.11,.004),white,.005)

# ---------------------------------------------------------------------------
# V3 contact model. The car follows an explicit kinematic redirection path
# (25 degree encroachment, the NCHRP 350 / MASH test angle). The rail is not a
# hand-placed bulge: on every frame its deflection is solved from the car's own
# world-space mesh points inside the rail height band, so the rail face sits on
# the car body (no gap, no interpenetration), spreads along the beam like a
# tensioned W-beam, and keeps a plastic residual after the car leaves.
# Still a CONCEPTUAL illustration, not a finite-element crash simulation.
# ---------------------------------------------------------------------------
FRAMES=90
CAR_SCALE=.85
RAIL_Z=.56; RAIL_H=.31            # W-beam 12.25in tall, top ~0.71 m like MGS 31in
RAIL_Y=.72                        # rail centreline, posts/blockouts behind (+Y)
NX=241; NZ=24
X0,X1=-16.0,8.0
SPREAD=1.9                        # beam tension spreads the pocket over posts

def rail_profile(u):
 return .060*math.cos((u-.5)*4*math.pi)+.018*math.cos((u-.5)*8*math.pi)
PMIN=min(rail_profile(j/(NZ-1)) for j in range(NZ))
RAIL_FACE=RAIL_Y+PMIN-.005

sys.path.insert(0,str(Path(__file__).resolve().parent))
from vehicle_geometry import verify_asset,prepare_graphite,legacy_metadata,make_wheels
variant=os.environ.get('VISUAL_VEHICLE_VARIANT','legacy')
asset=os.environ['VISUAL_V2_ASSET']
verify_asset(asset,variant)
assert os.path.isfile(asset)
before=set(bpy.context.scene.objects)
bpy.ops.import_scene.gltf(filepath=asset)
added=set(bpy.context.scene.objects)-before
assert len(added)>65,len(added)
# The public GLB includes one giant stray default Cube at (0,0,0). Remove.
for o in list(added):
 if o.type=='MESH' and o.name=='Cube' and o.dimensions.length>3.3:
  bpy.data.objects.remove(o,do_unlink=True);added.remove(o)
bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0))
car=bpy.context.object;car.name='CC0 detailed sedan animated as a rigid car'
for o in added:
 if o.parent is None or o.parent not in added:
  o.parent=car
  o.matrix_parent_inverse.identity()
print('IMPORTED_CC0_CAR_PARTS',len(added),flush=True)
bpy.context.view_layer.update()

# The CC0 sedan GLB has detached mirror shells/stalks. Anchor BOTH side
# assemblies to the cabin and connect their shells before generating motion.
# Do not hide stray parts: preserve full car geometry and prove attachment.
def closest_vertex_pair(source,target):
 pts=[target.matrix_world@v.co for v in target.data.vertices]
 tree=KDTree(len(pts))
 for idx,pt in enumerate(pts):tree.insert(pt,idx)
 tree.balance()
 best=None
 for vertex in source.data.vertices:
  p=source.matrix_world@vertex.co
  q,_,distance=tree.find(p)
  if best is None or distance<best[0]:best=(distance,p.copy(),q.copy())
 return best
def offset_mesh_instance(obj,delta):
 transform=obj.matrix_world.copy()
 transform.translation+=delta
 obj.matrix_world=transform
 bpy.context.view_layer.update()
if variant=='graphite':
 prepare_graphite(car)
else:
 for side in ('','.001'):
  arm=bpy.data.objects['Mirror arm'+side]
  shell=bpy.data.objects['Mirror shell'+side]
  body=bpy.data.objects['Cab and roof']
  distance,p,q=closest_vertex_pair(arm,body)
  assert distance>.05,('UNEXPECTED_MIRROR_IMPORT_GEOMETRY',side,distance)
  shift=.95*(q-p)
  offset_mesh_instance(arm,shift)
  offset_mesh_instance(shell,shift)
  _,p,q=closest_vertex_pair(shell,arm)
  offset_mesh_instance(shell,.93*(q-p))
  assert closest_vertex_pair(arm,body)[0]<.025,('MIRROR_STALK_DETACHED',side)
  assert closest_vertex_pair(shell,arm)[0]<.02,('MIRROR_SHELL_DETACHED',side)
 legacy_metadata(car)
print('MIRRORS_GEOMETRY_ANCHORED',flush=True)

car_meshes=[o for o in car.children_recursive if o.type=='MESH']
car_inv=car.matrix_world.inverted()
local_pts=[]
for o in car_meshes:
 m=car_inv@o.matrix_world
 local_pts+=[m@v.co for v in o.data.vertices]

# Look development of the CC0 sedan: replace toy-flat GLB materials with a
# coated metallic paint, real glass, rubber and machined metal.
def principled(m,color,metal,rough,coat=0,coat_rough=.05,spec=.5,trans=0):
 m.use_nodes=True
 p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 p.inputs['Base Color'].default_value=(*color,1)
 p.inputs['Metallic'].default_value=metal
 p.inputs['Roughness'].default_value=rough
 p.inputs['Coat Weight'].default_value=coat
 p.inputs['Coat Roughness'].default_value=coat_rough
 p.inputs['Specular IOR Level'].default_value=spec
 p.inputs['Transmission Weight'].default_value=trans
 return p
looks={'blue':((.26,.29,.32),.55,.38,.7,.04),'black':((.012,.013,.014),.0,.55,.3,.2),
 'chrome':((.80,.80,.80),1.0,.12,0,.05),'steel':((.20,.21,.22),.9,.38,0,.05),
 'rubber':((.018,.018,.019),.0,.82,0,.05),'glass':((.010,.013,.016),.0,.03,1.0,.0),
 'lamp':((.85,.86,.85),.0,.08,1.0,.02),'tail':((.45,.01,.01),.0,.12,1.0,.02),
 'white':((.75,.75,.72),.0,.5,0,.05)}
seen=set()
for o in car_meshes:
 for m in o.data.materials:
  if m and m.name in looks and m.name not in seen:
   seen.add(m.name);principled(m,*looks[m.name])

def smooth(e):
 e=min(max(e,0.),1.);return e*e*(3-2*e)
def pose(f):
 """Kinematic path: 25deg approach, contact, redirection parallel, exit."""
 x,y,h=float(os.environ.get('V3_X0','-2.95')),float(os.environ.get("V3_Y0","-1.10")),math.radians(25)
 out=[]
 for k in range(1,f+1):
  if k>1:
   e=min(max((k-12)/float(os.environ.get("V3_REDIR","48")),0.),1.)
   h=math.radians(25-33*e**float(os.environ.get("V3_POW","2.3" if variant=="graphite" else "3")))  # rail resistance turns the car parallel
   v=.070-.020*smooth(e)
   x+=v*math.cos(h);y+=v*math.sin(h)
  roll=0.0  # Rigid wheelbase: avoid driving the near tyres below the road.
  out.append((x,y,h,roll))
 return out
POSES=pose(FRAMES)
def car_matrix(p):
 x,y,h,roll=p
 return (Matrix.Translation((x,y,GROUND+.002))@Matrix.Rotation(math.pi/2+h,4,'Z')
  @Matrix.Rotation(-roll,4,'Y')@Matrix.Diagonal((CAR_SCALE,CAR_SCALE,CAR_SCALE,1)))
# Reuse the imported wheel meshes. Each axle-side assembly rotates about its
# measured tyre centre; preserve every child's existing car-local transform.
wheel_pivots=make_wheels(car)
# Keep wheels, tread, rotor assemblies and calipers on the unsprung chassis.
# Only the sprung assembly reacts; derive onset from geometric approach,
# then use the exact same body transform in both the rail solve and Blender.
body_pivot=None
body_local_points=[];unsprung_local_points=[]
from body_response import attach_body,local_matrix
if variant=='graphite':
 wheel_parts={ob for pivot in wheel_pivots for ob in pivot.children_recursive}
 for ob in car_meshes:
  target=unsprung_local_points if ob in wheel_parts or ob.name.startswith('Brake caliper') else body_local_points
  m=car.matrix_world.inverted()@ob.matrix_world
  target.extend(m@v.co for v in ob.data.vertices)
 onset=FRAMES
 for f,p in enumerate(POSES,1):
  M=car_matrix(p)
  rigid_world=[M@lp for lp in local_pts]
  envelope=[w.y for w in rigid_world if RAIL_Z-RAIL_H/2-.03<=w.z<=RAIL_Z+RAIL_H/2+.03]
  if envelope and RAIL_FACE-max(envelope)<=.03:
   onset=f;break
 assert onset<FRAMES,'BODY_CONTACT_ONSET_MISSING'
 body_pivot=attach_body(car,wheel_pivots,onset,FRAMES)
 print('BODY_RESPONSE_ONSET',onset,flush=True)
distance=0.
for f,p in enumerate(POSES,1):
 if f>1:distance+=math.hypot(p[0]-POSES[f-2][0],p[1]-POSES[f-2][1])
 for pivot in wheel_pivots:
  pivot.rotation_euler[0]=distance/(pivot['rolling_radius_local']*CAR_SCALE)
  pivot.keyframe_insert('rotation_euler',frame=f)
car.rotation_mode='XYZ'
for f,p in enumerate(POSES,1):
 car.matrix_world=car_matrix(p)
 car.keyframe_insert('location',frame=f)
 car.keyframe_insert('rotation_euler',frame=f)
 car.keyframe_insert('scale',frame=f)

# Contact solve per frame.
xs=[X0+(X1-X0)*i/(NX-1) for i in range(NX)]
dx=(X1-X0)/(NX-1)
zlo=RAIL_Z-RAIL_H/2-.03; zhi=RAIL_Z+RAIL_H/2+.03
gapdiag=[]
deflect=[]; contact=[]; prev=[0.]*NX; peak=[0.]*NX
for f,p in enumerate(POSES,1):
 M=car_matrix(p)
 body_transform=local_matrix(f,onset) if body_pivot else None
 frame_points=([body_transform@lp for lp in body_local_points]+unsprung_local_points) if body_pivot else local_pts
 env=[-9.]*NX
 for lp in frame_points:
  w=M@lp
  if zlo<=w.z<=zhi:
   i=int(round((w.x-X0)/dx))
   if 0<=i<NX and w.y>env[i]:env[i]=w.y
 push=[max(0.,e+.008-RAIL_FACE) for e in env]
 gapdiag.append(round(RAIL_FACE-max(env),3))
 hit=[i for i in range(NX) if push[i]>0]
 d=[max([push[k]*math.exp(-((xs[i]-xs[k])/SPREAD)**2) for k in hit] or [0.]) for i in range(NX)]
 # Plastic residual: once loaded the beam relaxes only to 70% of its peak.
 residual=[.70*peak[i]+(prev[i]-.70*peak[i])*.86 for i in range(NX)]
 d=[max(d[i],residual[i]) for i in range(NX)]
 # Match the actual sagged beam band, rather than letting vertices above
 # the beam create phantom contact as the rear of the car passes.
 world_points=[M@lp for lp in frame_points]
 for iteration in range(3):
  envelope=[-9.]*NX
  for w in world_points:
   i=int(round((w.x-X0)/dx))
   if 0<=i<NX and RAIL_Z-RAIL_H/2-.07*d[i]-.01<=w.z<=RAIL_Z+RAIL_H/2-.07*d[i]+.01:
    envelope[i]=max(envelope[i],w.y)
  actual_push=[max(0.,e+.008-RAIL_FACE) for e in envelope]
  loaded=[i for i in range(NX) if actual_push[i]>residual[i]]
  d=[max(residual[i],max([actual_push[k]*math.exp(-((xs[i]-xs[k])/SPREAD)**2) for k in loaded] or [0.])) for i in range(NX)]
 peak=[max(a,b) for a,b in zip(peak,d)]
 prev=d;deflect.append(d);contact.append(round(max(push),4))

vertices=[]; faces=[]
for i in range(NX):
 for j in range(NZ):
  u=j/(NZ-1)
  vertices.append((xs[i],RAIL_Y+rail_profile(u),RAIL_Z+(u-.5)*RAIL_H))
for i in range(NX-1):
 for j in range(NZ-1):
  a=i*NZ+j;faces.append((a,a+NZ,a+NZ+1,a+1))
mesh=bpy.data.meshes.new('corrugated galvanized steel W-beam surface')
mesh.from_pydata(vertices,[],faces);mesh.update()
rail=bpy.data.objects.new('Real 3D W-beam rail with car-contact solved deflection',mesh)
bpy.context.collection.objects.link(rail)
rail.data.materials.append(metal)
for p in rail.data.polygons:p.use_smooth=True
solid=rail.modifiers.new('steel sheet thickness','SOLIDIFY');solid.thickness=.010;solid.offset=1
bev=rail.modifiers.new('Fold edge rounding','BEVEL');bev.width=.006;bev.segments=2
rail.modifiers.new('Smooth normal interpolation','WEIGHTED_NORMAL')
rail.shape_key_add(name='undeformed')
for f,d in enumerate(deflect,1):
 key=rail.shape_key_add(name='contact frame %02d'%f)
 for i in range(NX):
  flat=1-.45*min(d[i]/.6,1)       # corrugation flattens under tension
  for j in range(NZ):
   u=j/(NZ-1)
   key.data[i*NZ+j].co=(xs[i],RAIL_Y+PMIN+(rail_profile(u)-PMIN)*flat+d[i],RAIL_Z+(u-.5)*RAIL_H-.07*d[i])
 for fr,val in ((f-1,0.),(f,1.),(f+1,0.)):
  if 1<=fr<=FRAMES:
   key.value=val;key.keyframe_insert('value',frame=fr)
def linear_animation(id_block):
 anim=id_block.animation_data
 if not anim or not anim.action:return
 action=anim.action
 if hasattr(action,'layers'):
  curves=[fc for layer in action.layers for strip in layer.strips
          for bag in strip.channelbags for fc in bag.fcurves]
 else:curves=action.fcurves
 for fc in curves:
  for kp in fc.keyframe_points:kp.interpolation='LINEAR'
linear_animation(rail.data.shape_keys)
linear_animation(car)
if body_pivot:linear_animation(body_pivot)
for pivot in wheel_pivots:linear_animation(pivot)

far=[]
for i in range(121):
 for j in range(NZ):
  u=j/(NZ-1)
  far.append((X0-60+60*i/120,RAIL_Y+rail_profile(u),RAIL_Z+(u-.5)*RAIL_H))
ff=[(i*NZ+j,(i+1)*NZ+j,(i+1)*NZ+j+1,i*NZ+j+1) for i in range(120) for j in range(NZ-1)]
fm=bpy.data.meshes.new('upstream W-beam continuation');fm.from_pydata(far,[],ff);fm.update()
farrail=bpy.data.objects.new('Upstream undisturbed W-beam run',fm)
bpy.context.collection.objects.link(farrail);farrail.data.materials.append(metal)
for p in fm.polygons:p.use_smooth=True
fs=farrail.modifiers.new('steel sheet thickness','SOLIDIFY');fs.thickness=.010;fs.offset=1
for x in [X0-1.1-1.9*n for n in range(32)]:
 b=box('Upstream steel post',(x,1.02,.11),(.15,.10,1.32),postmat,.012)
 box('Upstream blockout',(x,.85,RAIL_Z),(.15,.24,.30),darkmetal,.01)

def rail_d(f,x):
 d=deflect[f-1];t=(x-X0)/dx;i=min(int(t),NX-2);a=t-i
 return d[i]*(1-a)+d[i+1]*a

# Steel posts on 1.9 m (6 ft 3 in) spacing with blockouts, rotating about the
# soil pivot so their top follows the rail.
for k,x in enumerate([round(-15.2+1.9*n,2) for n in range(12)]):
 bpy.ops.object.empty_add(type='PLAIN_AXES',location=(x,1.02,-.55))
 pivot=bpy.context.object;pivot.name='Post soil pivot %d'%k
 b=box('Steel support post %d'%k,(0,0,0),(.15,.10,1.32),postmat,.012)
 b.parent=pivot;b.location=(0,0,.66)
 blk=box('Blockout %d'%k,(0,0,0),(.15,.24,.30),darkmetal,.01)
 blk.parent=pivot
 blk.location=(0,-.17,RAIL_Z+.55)
 # Keep the buried foot fixed and shear the post above it to the solved
 # beam displacement. The former rigid pivot shortened the horizontal
 # travel and dropped the bolt row below the sagged beam at peak load.
 # This remains geometric illustration, not a calibrated steel response.
 lever=RAIL_Z+.55
 b.shape_key_add(name='buried post basis')
 for f in range(1,FRAMES+1):
  d=rail_d(f,x)
  key=b.shape_key_add(name='post contact %02d'%f)
  for v,original in zip(key.data,b.data.vertices):
   weight=max(0.,(original.co.z+b.location.z)/lever)
   v.co=original.co+Vector((0,d*weight,-.07*d*weight))
  for fr,val in ((f-1,0.),(f,1.),(f+1,0.)):
   if 1<=fr<=FRAMES:
    key.value=val;key.keyframe_insert('value',frame=fr)
 linear_animation(b.data.shape_keys)
 for f in range(1,FRAMES+1):
  d=rail_d(f,x)
  blk.location=(0,-.17+d,lever-.07*d)
  blk.keyframe_insert('location',frame=f)
 linear_animation(blk)
 for dz in (-.08,.08):
  c=cylinder('W-beam splice bolt head',(0,0,0),.022,.03,rim,(math.pi/2,0,0),16)
  c.parent=pivot
  u=(dz/RAIL_H)+.5
  for f in range(1,FRAMES+1):
   d=rail_d(f,x)
   flat=1-.45*min(d/.6,1)
   # The corrugation flattens as well as translating: carry each bolt
   # with its own row on the beam, rather than moving a rigid bolt group.
   face=RAIL_Y+PMIN+(rail_profile(u)-PMIN)*flat
   c.location=(0,face-.008-1.02+d,lever+dz-.07*d)
   c.keyframe_insert('location',frame=f)
  linear_animation(c)
 cylinder('post ground contact ring',(x,1.02,GROUND+.01),.15,.03,shoulder)

# Fixed world-space pale cyan contour = undeformed rail top edge, used only to
# communicate relative movement. NOT a physical duplicate guardrail.
glow=bpy.data.materials.new('SCREEN GUIDE - cyan reference, not real guardrail')
glow.use_nodes=True
gn=glow.node_tree.nodes
gn.clear()
go=gn.new('ShaderNodeOutputMaterial')
em=gn.new('ShaderNodeEmission')
em.inputs['Color'].default_value=(.035,.48,.62,1)
em.inputs['Strength'].default_value=.6
glow.node_tree.links.new(em.outputs['Emission'],go.inputs['Surface'])
curve=bpy.data.curves.new('Undeformed rail reference contour','CURVE')
curve.dimensions='3D'
curve.bevel_depth=.012
curve.bevel_resolution=3
spline=curve.splines.new('POLY')
spline.points.add(71)
for i,pt in enumerate(spline.points):
 pt.co=(-6.5+i*11.0/71,RAIL_FACE,GROUND+.004,1)
guide=bpy.data.objects.new('UNDISTORTED_REFERENCE_RAIL_CONTOUR_CYAN',curve)
bpy.context.collection.objects.link(guide)
guide.data.materials.append(glow)

# Physical daylight: procedural sky for real reflections on paint and steel.
world=bpy.data.worlds.new('procedural daylight sky')
scene.world=world;world.use_nodes=True
wn=world.node_tree.nodes
wn['Background'].inputs['Color'].default_value=(.42,.52,.62,1)
wn['Background'].inputs['Strength'].default_value=.55
bpy.ops.object.light_add(type='SUN',location=(0,0,7))
sun=bpy.context.object;sun.name='key sun';sun.data.energy=3.2
sun.data.angle=math.radians(1.2)
sun.rotation_euler=(math.radians(52),0,math.radians(205-180))
def area(name,loc,energy,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc)
 lamp=bpy.context.object;lamp.name=name;lamp.data.energy=energy
 lamp.data.shape='DISK';lamp.data.size=size;point(lamp,target)
area('soft paint highlight card',(-3,-6,6),900,6.0,(0,0,.5))
scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=float(os.environ.get('V3_EXPOSURE','-1.0'))

cam_loc=Vector(tuple(float(v) for v in os.environ.get('V3_CAM','7.5,-2.4,6.2').split(',')))
cam_tgt=Vector(tuple(float(v) for v in os.environ.get('V3_TGT','-1.9,-.2,.35').split(',')))
bpy.ops.object.camera_add(location=cam_loc)
cam=bpy.context.object;cam.name='FIXED hero 3/4 CC0 car + guardrail'
point(cam,cam_tgt)
cam.data.type='PERSP';cam.data.lens=float(os.environ.get('V3_LENS','19.3' if variant=='graphite' else '20'))
cam.data.sensor_fit='VERTICAL'
scene.camera=cam
scene['support_motion_style']='buried-foot shear with corrugation-following bolts'
scene['primary_contact_frames']=[12,48]
scene['v3_contact_push_m']=contact
scene['v3_peak_deflection_m']=round(max(peak),3)
print('V3_CONTACT_PUSH',contact,flush=True)
print('V3_GAP',gapdiag[::3],flush=True)
print('V3_POSE',[tuple(round(v,2) for v in POSES[f-1]) for f in (1,14,22,40,60,90)],flush=True)
print('V3_PEAK_DEFLECTION_M',round(max(peak),3),'RESIDUAL_M',round(max(deflect[-1]),3),flush=True)
for obj in scene.objects:
 if obj.name.startswith('Post soil pivot'):linear_animation(obj)
scene.render.filepath=str(OUT/'frame_')
scene.frame_set(1 if mode=='scene' else 40)
blend=OUT/'guardrail_v2_local.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
if mode=='scene':
 print('SAVED_SCENE_ONLY_NO_RENDER',blend,flush=True)
else:
 scene.render.resolution_percentage=res
 scene.cycles.samples=samples
 for f in (1,22,40):
  scene.frame_set(f)
  scene.render.filepath=str(OUT/('preview_%02d.png'%f))
  bpy.ops.render.render(write_still=True)
print('BLENDER_DONE',mode,flush=True)
