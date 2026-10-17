# Benchmark copy of locally authored guardrail Blender 3D scene. No production engine modification.
# CC0 Sedan asset from Innerscene, asset hash pinned in the workflow.
# Conceptual kinematics ONLY; no real-world crash-test validation.
#!/usr/bin/env python3
"""Premium look-development proof. Conceptual guardrail mechanics, not crash simulation.
Requires Blender 5.0+, Cycles CPU. Assets and geometry created procedurally.
"""
import bpy, math, sys, os
from mathutils import Vector
from pathlib import Path

OUT=Path(os.environ.get('BLENDER_BENCH_OUT', '/tmp/blender-guardrail-bench'))
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
scene.cycles.samples=samples
scene.cycles.use_denoising=True
scene.render.resolution_x=1080
scene.render.resolution_y=1920
scene.render.resolution_percentage=res
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
  n.inputs['Detail'].default_value=3
  b=nodes.new('ShaderNodeBump')
  b.inputs['Strength'].default_value=.20
  b.inputs['Distance'].default_value=bump
  links.new(n.outputs['Fac'],b.inputs['Height'])
  links.new(b.outputs['Normal'],p.inputs['Normal'])
 return m
metal=mat('ZINC - galvanized W-beam steel',(0.43,.48,.50),.85,.30,125,.014)
postmat=mat('Posts - hot dipped galvanized steel',(.29,.33,.35),.83,.37,140,.012)
darkmetal=mat('Black underbody metal',(.11,.14,.17),.7,.26)
paint=mat('Blue teal metallic car paint',(.028,.28,.35),.67,.21)
glass=mat('Tinted glass',(.055,.13,.17),.6,.14)
rubber=mat('Soft black tire rubber',(.013,.016,.018),.02,.86,38,.02)
road=mat('Fine gritty black asphalt',(.075,.075,.070),.0,.94,240,.025)
shoulder=mat('Dry rocky soil',(.24,.19,.125),0,.96,170,.04)
grass=mat('Muted roadside vegetation',(.09,.14,.06),0,.95,115,.05)
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

# Road surface and shoulder -- physically separated materials.
box('dark fine-grain asphalt roadway',(0,-2.3,-.18),(22,6.0,.27),road,.035)
box('gritty soil shoulder',(0,1.85,-.23),(22,2.6,.37),shoulder,.055)
box('green grass at back',(0,3.6,-.23),(22,1.6,.35),grass,.05)
box('white road edge marking',(0,-.53,-.027),(22,.092,.006),white,.004)
for i in range(-7,8,2):
 box('intermittent dashed line', (i,-3.66,-.021),(1.05,.095,.004),white,.005)

# Guardrail W-beam: true 3D corrugated profile with Solidify and shape-key deformation.
# W-beam face lies along X and is vertically corrugated in cross-section.
NX=88; NZ=24
X0,X1=-7.1,7.1
vertices=[]; faces=[]
for i in range(NX):
 x=X0+(X1-X0)*i/(NX-1)
 for j in range(NZ):
  u=j/(NZ-1)
  z=.80+(u-.5)*.33
  # Four distinct longitudinal folds; sheet is thin steel rather than generic ribbon.
  y=.70 + .060*math.cos((u-.5)*4*math.pi) + .018*math.cos((u-.5)*8*math.pi)
  vertices.append((x,y,z))
for i in range(NX-1):
 for j in range(NZ-1):
  a=i*NZ+j;faces.append((a,a+NZ,a+NZ+1,a+1))
mesh=bpy.data.meshes.new('corrugated galvanized steel W-beam surface')
mesh.from_pydata(vertices,[],faces);mesh.update()
rail=bpy.data.objects.new('Real 3D W-beam rail with elastic/plastic proxy deflection',mesh)
bpy.context.collection.objects.link(rail)
rail.data.materials.append(metal)
for p in rail.data.polygons:p.use_smooth=True
solid=rail.modifiers.new('steel sheet thickness','SOLIDIFY');solid.thickness=.010
bev=rail.modifiers.new('Fold edge rounding','BEVEL');bev.width=.008;bev.segments=2
rail.modifiers.new('Smooth normal interpolation','WEIGHTED_NORMAL')
basekey=rail.shape_key_add(name='undeformed')
deform=rail.shape_key_add(name='impact deflection - CONCEPTUAL')
for v,vert in zip(deform.data,vertices):
 x,y,z=vert
 amp=.52*math.exp(-((x-0.0)/1.45)**2)
 v.co.y=y+amp
for fr,value in [(1,0),(9,0),(21,.55),(35,1.0),(53,.92),(75,.66),(90,.58)]:
 deform.value=value;deform.keyframe_insert(data_path='value',frame=fr)

# Five steel posts embedded in shoulder. Each pivots about a below-surface origin.
for k,x in enumerate([-5.4,-3.25,-1.1,1.1,3.25,5.4]):
 b=box('Steel support post %d'%k,(x,.85,.16),(.16,.16,1.87),postmat,.018)
 b.data.materials[0]=postmat
 # Rotate about lower/soil base, not center: location parented to empty.
 bpy.ops.object.empty_add(type='PLAIN_AXES',location=(x,.85,-.45))
 pivot=bpy.context.object;pivot.name='Post soil pivot %d'%k
 b.parent=pivot;b.matrix_parent_inverse.identity();b.location=(0,0,.90)
 influence=math.exp(-(x/2.1)**2)
 for fr,ang in [(1,0),(10,0),(34,-.18*influence),(55,-.16*influence),(90,-.11*influence)]:
  pivot.rotation_euler[0]=ang
  pivot.keyframe_insert('rotation_euler',frame=fr)
 # Bolt and washer on rail face front (toward moving car).
 for dz in [-.08,.08]:
  cylinder('W-beam bolt head', (x,.56,.80+dz),.046,.026,rim,(math.pi/2,0,0),16)
 # At the soil surface (small anchor shadow ring, physically illustrative).
 cylinder('post ground contact ring',(x,.85,-.01),.17,.032,shoulder)

# High-detail unbranded CC0 sedan: real Blender mesh with doors, glass, wheels, lamps.
# Verified original: https://www.innerscene.com/tools/library/3d-parts/sedan-car-42109739
# GLB metadata: "Sedan car" original Innerscene, CC0-1.0, sha256 4cb896f...b25d3.
asset=os.environ['BLENDER_BENCH_ASSET']
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
# Original GLB front points along negative Y; rotate 90 degrees to positive X.
car.scale=(.75,.75,.75)
for frame,x,y,heading in [(1,-.68,-.43,.12),(12,-.52,-.28,.10),(23,-.35,-.10,.06),
 (35,-.10,-.05,.03),(55,.29,-.33,-.06),(74,.59,-.52,-.09),(90,.94,-.70,-.10)]:
 car.location=(x,y,0)
 car.rotation_euler[2]=math.pi/2+heading
 car.keyframe_insert('location',frame=frame)
 car.keyframe_insert('rotation_euler',frame=frame)
print('IMPORTED_CC0_CAR_PARTS',len(added),flush=True)

# Reused photorealistic lighting stage, fixed deliberate composition.
world=bpy.data.worlds.new('neutral blue-grey outdoor skylight')
scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.37,.45,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
def area(name,loc,energy,color,size,target=(0,0,.75)):
 bpy.ops.object.light_add(type='AREA',location=loc)
 lamp=bpy.context.object;lamp.name=name;lamp.data.energy=energy;lamp.data.color=color
 lamp.data.shape='DISK';lamp.data.size=size
 point(lamp,target)
 return lamp
area('giant soft cinematic daylight',(-1.5,-2.8,7.5),900,(1.0,.9,.78),6.0)
area('metal rim highlight',(1.0,2.8,5.0),1300,(.70,.83,1.0),4.5)
area('front vehicle body fill',(4.0,-4.0,3.7),750,(.78,.90,1.0),4.0)
bpy.ops.object.light_add(type='SUN',location=(0,0,7))
sun=bpy.context.object;sun.name='long golden sun';sun.data.energy=1.2
sun.data.angle=math.radians(7)
sun.rotation_euler=(math.radians(32),math.radians(-30),math.radians(-32))

bpy.ops.object.camera_add(location=(3.9,-8.5,4.05))
cam=bpy.context.object;cam.name='FIXED hero 3/4 CC0 car + guardrail'
point(cam,(0,-.1,.70))
cam.data.type='PERSP';cam.data.lens=31
cam.data.sensor_fit='VERTICAL'
scene.camera=cam
scene.render.image_settings.color_mode='RGBA'
scene.render.filepath=str(OUT/'frame_')
scene.render.image_settings.file_format='PNG'
frame_index=int(args[3]) if len(args)>3 else 42
scene.frame_set(frame_index if mode=='still' else 1)
blend=OUT/'guardrail_3d_lookdev.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
if mode=='still':
 scene.render.filepath=str(OUT/f'frame_{frame_index:04d}.png')
 print('RENDER_STILL',res,samples,flush=True)
 bpy.ops.render.render(write_still=True)
else:
 scene.render.filepath=str(OUT/'seq_')
 print('RENDER_ANIMATION',res,samples,flush=True)
 bpy.ops.render.render(animation=True)
print('BLENDER_DONE',mode,flush=True)

