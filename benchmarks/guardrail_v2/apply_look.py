"""Reuse verified CC0 Poly Haven lighting/asphalt, keeping the fixed motion camera."""
import bpy,os,hashlib,sys
from pathlib import Path
s=bpy.context.scene
Path(os.environ['VISUAL_V2_OUTPUT']).mkdir(parents=True,exist_ok=True)
assets=Path(os.environ['VISUAL_LOOK_ASSETS'])
files={'suburban_field_01_1k.hdr':'785278f45fbe4714782d7f291e6abc9e58f1d705c2c2fe3743d11eee63f34ea5',
'asphalt_01_diff_1k.jpg':'99b6f6bdfbd09279f3f550ac9593336df541aa2319537566eeb3e737d8512010'}
for name,digest in files.items():assert hashlib.sha256((assets/name).read_bytes()).hexdigest()==digest,name
world=s.world;world.use_nodes=True
nodes=world.node_tree.nodes;links=world.node_tree.links;nodes.clear()
env=nodes.new('ShaderNodeTexEnvironment')
env.image=bpy.data.images.load(str(assets/'suburban_field_01_1k.hdr'),check_existing=True)
bg=nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.6
output=nodes.new('ShaderNodeOutputWorld')
links.new(env.outputs['Color'],bg.inputs['Color'])
# HDRI lights/reflections only; the visible background stays synthetic.
camera_bg=nodes.new('ShaderNodeBackground');camera_bg.inputs['Color'].default_value=(.35,.45,.6,1)
camera_bg.inputs['Strength'].default_value=.6
ray=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader')
links.new(ray.outputs['Is Camera Ray'],mix.inputs[0])
links.new(bg.outputs['Background'],mix.inputs[1]);links.new(camera_bg.outputs['Background'],mix.inputs[2])
links.new(mix.outputs[0],output.inputs['Surface'])
for ob in s.objects:
 if ob.type=='LIGHT':
  if ob.name=='key sun':ob.data.energy=1.25
  elif ob.name=='soft paint highlight card':ob.data.energy=260
s.view_settings.exposure=-.22
road=bpy.data.materials['Fine gritty black asphalt']
n=road.node_tree.nodes;l=road.node_tree.links
p=next(x for x in n if x.type=='BSDF_PRINCIPLED')
coord=n.new('ShaderNodeTexCoord')
scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=.48
l.new(coord.outputs['Object'],scale.inputs[0])
tex=n.new('ShaderNodeTexImage');tex.extension='REPEAT'
tex.image=bpy.data.images.load(str(assets/'asphalt_01_diff_1k.jpg'),check_existing=True)
l.new(scale.outputs['Vector'],tex.inputs['Vector']);l.new(tex.outputs['Color'],p.inputs['Base Color'])
p.inputs['Roughness'].default_value=.9
paint=bpy.data.materials.get('paint') or bpy.data.materials['blue'];p=next(n for n in paint.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
p.inputs['Base Color'].default_value=(.045,.13,.23,1)
p.inputs['Metallic'].default_value=.6;p.inputs['Roughness'].default_value=.25;p.inputs['Coat Weight'].default_value=.65
car=bpy.data.objects['CC0 detailed sedan animated as a rigid car']
if car.get('vehicle_variant')=='graphite':
 # The reused source glass is named glass.001 and carries 94% transmission.
 # Use deliberate opaque tinted explainer glazing, matching the legacy look.
 glazing=[]
 for material in bpy.data.materials:
  if material.name.split('.')[0]!='glass' or not material.users:continue
  pp=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
  pp.inputs['Base Color'].default_value=(.015,.025,.035,1)
  pp.inputs['Alpha'].default_value=1
  pp.inputs['Transmission Weight'].default_value=0
  pp.inputs['Metallic'].default_value=0
  pp.inputs['Roughness'].default_value=.12
  pp.inputs['Coat Weight'].default_value=.25
  pp.inputs['Specular IOR Level'].default_value=.35
  glazing.append(material.name)
 assert glazing,'GRAPHITE_GLAZING_NOT_FOUND'
 s['glazing_style']='opaque_tint_no_transmission'
 print('GRAPHITE_GLAZING_NORMALIZED',glazing,flush=True)

 sys.path.insert(0,str(Path(__file__).resolve().parent))
 from landscape import apply_landscape
 apply_landscape(s)
# The undeformed guide remains in geometry QA; the new styled view hides it.

bpy.ops.file.pack_all()
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(Path(os.environ['VISUAL_V2_OUTPUT'])/'guardrail_v2_local.blend'))
print('LICENSED_LOOK_APPLIED',flush=True)
