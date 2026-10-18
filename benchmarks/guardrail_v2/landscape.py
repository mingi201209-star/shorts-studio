"""Deterministic low-cost roadside geometry; nothing enters the contact corridor."""
import bpy,math,random
from mathutils import Vector
def apply_landscape(scene):
 ground=-.045
 # Paint follows the asphalt surface instead of hovering centimetres above it.
 for ob in scene.objects:
  if ob.name.startswith(('white road edge marking','intermittent dashed line')):
   ob.location.z=ground+.0005;ob.dimensions.z=.001
   for mod in ob.modifiers:
    if mod.type=='BEVEL':mod.width=.0002
 old=scene.objects.get('green grass at back')
 if old:old.hide_render=True
 mat=bpy.data.materials['Muted roadside vegetation']
 n=mat.node_tree.nodes;l=mat.node_tree.links
 p=next(x for x in n if x.type=='BSDF_PRINCIPLED')
 tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=.35
 coord=n.new('ShaderNodeTexCoord');l.new(coord.outputs['Object'],tex.inputs['Vector'])
 ramp=n.new('ShaderNodeValToRGB')
 ramp.color_ramp.elements[0].color=(.055,.08,.025,1)
 ramp.color_ramp.elements[1].color=(.20,.24,.095,1)
 l.new(tex.outputs['Fac'],ramp.inputs['Fac']);l.new(ramp.outputs['Color'],p.inputs['Base Color'])
 def height(x,y):
  w=min(max((y-3.12)/16,0),1)
  return ground+w*(.55+.45*math.sin(x/17+y/22)+.24*math.sin(x/8-y/19))
 nx,ny=81,31
 verts=[(-120+240*i/(nx-1),3.12+87*j/(ny-1),height(-120+240*i/(nx-1),3.12+87*j/(ny-1))) for i in range(nx) for j in range(ny)]
 faces=[(i*ny+j,(i+1)*ny+j,(i+1)*ny+j+1,i*ny+j+1) for i in range(nx-1) for j in range(ny-1)]
 mesh=bpy.data.meshes.new('rolling roadside terrain');mesh.from_pydata(verts,[],faces);mesh.update()
 ob=bpy.data.objects.new('Rolling roadside field',mesh);scene.collection.objects.link(ob);mesh.materials.append(mat)
 for f in mesh.polygons:f.use_smooth=True
 rng=random.Random(20261018)
 # Short geometric grass blades keep the W-beam/contact area unobstructed.
 grassmats=[]
 for i,col in enumerate(((.10,.14,.04,1),(.18,.22,.07,1),(.25,.25,.11,1))):
  m=bpy.data.materials.new('Roadside blade '+str(i));m.diffuse_color=col
  m.use_nodes=True;q=m.node_tree.nodes.get('Principled BSDF')
  q.inputs['Base Color'].default_value=col;q.inputs['Roughness'].default_value=.95
  grassmats.append(m)
 gv=[];gf=[];mi=[]
 for k in range(600):
  x=rng.uniform(-28,18);y=rng.uniform(1.65,12)
  z=height(x,y) if y>=3.12 else ground
  for j in range(3):
   angle=rng.random()*2*math.pi;h=rng.uniform(.06,.19);w=rng.uniform(.009,.019)
   dx=math.cos(angle)*w;dy=math.sin(angle)*w
   i=len(gv);gv.extend(((x-dx,y-dy,z),(x+dx,y+dy,z),(x+dx*.6,y+dy*.6,z+h)))
   gf.append((i,i+1,i+2));mi.append(rng.randrange(len(grassmats)))
 mesh=bpy.data.meshes.new('sparse roadside grass blades');mesh.from_pydata(gv,[],gf);mesh.update()
 ob=bpy.data.objects.new('Sparse short verge grass',mesh);scene.collection.objects.link(ob)
 for m in grassmats:mesh.materials.append(m)
 for f,i in zip(mesh.polygons,mi):f.material_index=i
 # Reuse one low-poly pebble mesh across linked instances.
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1)
 stone=bpy.context.object;stone.name='Shoulder pebble prototype'
 stone.data.materials.append(bpy.data.materials['Dry rocky soil'])
 for k in range(70):
  ob=stone if k==0 else bpy.data.objects.new('Shoulder pebble '+str(k),stone.data)
  if k:scene.collection.objects.link(ob)
  r=rng.uniform(.018,.045)
  ob.location=(rng.uniform(-18,10),rng.uniform(1.45,3.05),ground+r*.3)
  ob.scale=(r*1.3,r,r*.45);ob.rotation_euler.z=rng.random()*math.pi
 guide=scene.objects.get('UNDISTORTED_REFERENCE_RAIL_CONTOUR_CYAN')
 if guide:guide.hide_render=True
 scene['landscape_variant']='rolling_field_verge_v1'
 print('LANDSCAPE_APPLIED',len(verts),len(gv),'contact corridor clear',flush=True)
