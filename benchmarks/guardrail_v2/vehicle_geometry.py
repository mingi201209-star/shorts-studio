"""Adapters for the two pinned CC0 sedan assets; Blender's importer remains authoritative."""
import bpy,math,json,hashlib
from mathutils import Matrix,Vector
from mathutils.kdtree import KDTree

DIGESTS={'legacy':'4cb896f740de4da871c1d87c4af2b734db3d1e8fac852e308f1fca03a63b25d3',
'graphite':'feb0be31d153ddb42dc15ae52a651e214e85ab67e31bec4282b00f9d47c9b597'}

def verify_asset(path,variant):
 assert variant in DIGESTS,('UNKNOWN_ASSET_VARIANT',variant)
 assert hashlib.sha256(open(path,'rb').read()).hexdigest()==DIGESTS[variant],'ASSET_SHA_MISMATCH'

def nearest(source,target):
 tree=KDTree(len(target.data.vertices))
 for i,v in enumerate(target.data.vertices):tree.insert(target.matrix_world@v.co,i)
 tree.balance()
 best=None
 for v in source.data.vertices:
  p=source.matrix_world@v.co;q,_,d=tree.find(p)
  if best is None or d<best[0]:best=(d,p.copy(),q.copy())
 return best

def prepare_graphite(car):
 meshes=[o for o in car.children_recursive if o.type=='MESH']
 assert len(meshes)==304,('GRAPHITE_PART_COUNT',len(meshes))
 # Source forward=-X; project convention forward=-Y. Preserve every mesh.
 old={o.name:o.matrix_world.copy() for o in meshes}
 R=Matrix.Rotation(math.pi/2,4,'Z')
 for o in meshes:
  o.parent=car;o.matrix_parent_inverse.identity();o.matrix_basis=R@old[o.name]
 bpy.context.view_layer.update()
 tyres=sorted([o for o in meshes if 'Sculpted_tyre' in o.name],key=lambda o:o.name)
 assert len(tyres)==4
 floor=min((o.matrix_local@v.co).z for o in tyres for v in o.data.vertices)
 for o in meshes:o.location.z-=floor
 bpy.context.view_layer.update()
 connections=[]
 for suffix in ('','.001'):
  plinth=bpy.data.objects['Short mirror plinth'+suffix]
  housing=bpy.data.objects['Aerodynamic mirror lower housing'+suffix]
  cap=bpy.data.objects['Aerodynamic mirror painted cap'+suffix]
  insert=bpy.data.objects['Mirror reflective insert'+suffix]
  body=bpy.data.objects['Watertight 14-station body shell']
  # The support joins the body shell, not the slanted A pillar above it.
  distance,p,q=nearest(plinth,body)
  if distance>.025:
   delta=.95*(q-p)
   for ob in (plinth,housing,cap,insert):ob.location+=delta
   bpy.context.view_layer.update()
  for a,b,limit in ((plinth,body,.025),(housing,plinth,.025),(cap,housing,.02),(insert,housing,.02)):
   gap=nearest(a,b)[0]
   assert gap<limit,('GRAPHITE_MIRROR_ATTACHMENT',a.name,b.name,gap)
   connections.append([a.name,b.name,limit])
 car['mirror_connections_json']=json.dumps(connections)
 car['tyre_names_json']=json.dumps([o.name for o in tyres])
 car['vehicle_variant']='graphite'
 print('GRAPHITE_NORMALIZED',len(meshes),'tyre_floor_offset',round(floor,6),flush=True)

def legacy_metadata(car):
 connections=[]
 for suffix in ('','.001'):
  connections += [['Mirror arm'+suffix,'Cab and roof',.025],['Mirror shell'+suffix,'Mirror arm'+suffix,.02]]
 car['mirror_connections_json']=json.dumps(connections)
 car['tyre_names_json']=json.dumps(['Front_tire','Front_tire.001','Rear_tire','Rear_tire.001'])
 car['vehicle_variant']='legacy'

def mirror_connections(car):
 if 'mirror_connections_json' in car:return json.loads(car['mirror_connections_json'])
 # Historic saved baseline scenes retain the exact original checks.
 return [[a+s,b,limit] for s in ('','.001') for a,b,limit in [('Mirror arm','Cab and roof',.025),('Mirror shell','Mirror arm'+s,.02)]]

def tyre_objects(car):
 if 'tyre_names_json' in car:names=json.loads(car['tyre_names_json'])
 else:names=['Front_tire','Front_tire.001','Rear_tire','Rear_tire.001']
 assert len(names)==len(set(names))==4,'FOUR_TYRES_REQUIRED'
 return [bpy.data.objects[name] for name in names]

def make_wheels(car):
 meshes=[o for o in car.children_recursive if o.type=='MESH']
 tyres=tyre_objects(car)
 centres={}
 for tyre in tyres:
  bounds=[tyre.matrix_local@Vector(v) for v in tyre.bound_box]
  centres[tyre.name]=sum(bounds,Vector())/len(bounds)
 if car['vehicle_variant']=='graphite':
  moving=[o for o in meshes if o.name.startswith('107 reused ') or o.name.startswith(('Brake rotor','Ventilated brake rotor','Rotor drill recess','Siped tread blocks'))]
 else:moving=[o for o in meshes if o.name.startswith(('Front_','Rear_'))]
 assert all(o in moving for o in tyres)
 assigned={name:[] for name in centres}
 for ob in moving:
  b=[ob.matrix_local@Vector(v) for v in ob.bound_box];mid=sum(b,Vector())/len(b)
  name=min(centres,key=lambda k:(mid-centres[k]).length)
  assert (mid-centres[name]).length<.4,('WHEEL_COMPONENT_TOO_FAR',ob.name,name)
  assigned[name].append(ob)
 pivots=[]
 for i,tyre in enumerate(tyres):
  centre=centres[tyre.name]
  bounds=[tyre.matrix_local@Vector(v) for v in tyre.bound_box]
  radius=(max(v.z for v in bounds)-min(v.z for v in bounds))/2
  bpy.ops.object.empty_add(type='PLAIN_AXES')
  pivot=bpy.context.object;pivot.name='WheelPivot_'+str(i)
  pivot.parent=car;pivot.location=centre
  pivot['rolling_radius_local']=radius;pivot['tyre_name']=tyre.name
  for ob in assigned[tyre.name]:
   old=ob.matrix_local.copy();ob.parent=pivot;ob.matrix_parent_inverse.identity()
   ob.matrix_basis=Matrix.Translation(-centre)@old
  assert tyre.parent==pivot
  pivots.append(pivot)
 return pivots


def clear_wheelhouse_liners(car):
 """Retain the imported outer arch; thin its inward-facing lining for travel."""
 tyres=tyre_objects(car)
 inv_car=car.matrix_world.inverted()
 def transform(ob):return inv_car@ob.matrix_world
 def centre(ob):return sum((transform(ob)@Vector(p) for p in ob.bound_box),Vector())/8
 centres={t.name:centre(t) for t in tyres}
 liners=[o for o in car.children_recursive if o.name.startswith('Wheelhouse inner liner')]
 assert len(liners)==4,'FOUR_WHEELHOUSE_LINERS_REQUIRED'
 for ob in liners:
  mid=centre(ob);c=min(centres.values(),key=lambda p:(p-mid).length)
  m=transform(ob);inv=m.inverted()
  points=[m@v.co for v in ob.data.vertices]
  radii=[math.hypot(p.y-c.y,p.z-c.z) for p in points]
  inner,outer=min(radii),max(radii)
  assert .3<inner<outer<.5 and outer-inner>.012,('UNEXPECTED_LINER_PROFILE',ob.name,inner,outer)
  for vertex,p,radius in zip(ob.data.vertices,points,radii):
   cleared=outer-.012*(outer-radius)/(outer-inner)
   p.y=c.y+(p.y-c.y)*cleared/radius;p.z=c.z+(p.z-c.z)*cleared/radius
   vertex.co=inv@p
  ob.data.update()
  ob['source_inner_radius_m']=inner;ob['preserved_outer_radius_m']=outer
  print('WHEELHOUSE_LINER_CLEARANCE',ob.name,round(inner,5),round(outer-.012,5),round(outer,5),flush=True)
