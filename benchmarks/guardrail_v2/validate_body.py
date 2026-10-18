"""Independent sprung-body timing, limits and wheel-assembly audit."""
import bpy, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from vehicle_geometry import tyre_objects


def body_errors(scene, car, contacts):
    if car.get('vehicle_variant') != 'graphite':
        return [], []
    errors, rows = [], []
    body=bpy.data.objects.get('SprungBody_contact_response')
    if body is None:
        return [{'frame':0,'check':'BODY_RESPONSE_MISSING','value':None}], []
    first_contact=next((r['frame'] for r in contacts if r['contact_gap_m'] is not None and r['contact_gap_m']<=.03),None)
    scene.frame_set(scene.frame_start);bpy.context.view_layer.update()
    tyres=tyre_objects(car)
    def centre(ob):return sum((ob.matrix_world@Vector(v) for v in ob.bound_box),Vector())/8
    arches=[o for o in car.children_recursive if o.name.startswith(('Rolled fender lip','Wheelhouse inner liner'))]
    if len(arches)!=8:
        errors.append({'frame':0,'check':'WHEEL_ARCH_MISSING','value':len(arches)})
    pairs=[(min(tyres,key=lambda t:(centre(t)-centre(a)).length),a) for a in arches]
    def tree(objects):
        vertices=[];polygons=[]
        for ob in objects:
            offset=len(vertices)
            vertices.extend(ob.matrix_world@v.co for v in ob.data.vertices)
            polygons.extend(tuple(offset+i for i in p.vertices) for p in ob.data.polygons)
        return BVHTree.FromPolygons(vertices,polygons)
    wheel_members={t.name:[t]+[o for o in t.parent.children if o.name.startswith('Siped tread blocks')] for t in tyres}
    first_motion=None;last=None
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        angles=body.rotation_euler
        magnitude=math.degrees(math.hypot(angles.x,angles.y))
        heave=body.location.z-.45
        if magnitude>.02 and first_motion is None:first_motion=frame
        if first_contact is not None and frame<first_contact and (magnitude>.02 or abs(heave)>.0001):
            errors.append({'frame':frame,'check':'BODY_REACTS_BEFORE_CONTACT','value':magnitude})
        step=math.degrees(body.rotation_euler.to_quaternion().rotation_difference(last).angle) if last else 0.
        if magnitude>3 or not -.02<=heave<=.005 or step>.8:
            errors.append({'frame':frame,'check':'BODY_RESPONSE_JUMP','value':[magnitude,heave,step]})
        wheel_trees={t.name:tree(wheel_members[t.name]) for t in tyres}
        intersections=0
        for tyre,arch in pairs:
            count=len(wheel_trees[tyre.name].overlap(tree([arch])))
            intersections+=count
            if count:
                errors.append({'frame':frame,'check':'WHEEL_ARCH_INTERSECTION','value':[tyre.name,arch.name,count]})
        rows.append({'frame':frame,'wheel_arch_intersections':intersections,'body_angle_degrees':round(magnitude,5),'heave_m':round(heave,6),'angle_step_degrees':round(step,5)})
        last=body.rotation_euler.to_quaternion()
    if max(r['body_angle_degrees'] for r in rows)<.6:
        errors.append({'frame':0,'check':'BODY_RESPONSE_ABSENT','value':first_motion})
    if rows[-1]['body_angle_degrees']>.08 or abs(rows[-1]['heave_m'])>.001:
        errors.append({'frame':scene.frame_end,'check':'BODY_RESPONSE_NOT_SETTLED','value':rows[-1]})
    for prefix,count in [('Siped tread blocks',4),('Ventilated brake rotor',4),('Rotor drill recess',72)]:
        parts=[o for o in car.children_recursive if o.type=='MESH' and o.name.startswith(prefix)]
        if len(parts)!=count or any(o.parent is None or not o.parent.name.startswith('WheelPivot_') for o in parts):
            errors.append({'frame':0,'check':'WHEEL_ASSEMBLY_DETACHED','value':prefix})
    return errors,rows
