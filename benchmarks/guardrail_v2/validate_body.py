"""Independent sprung-body timing, limits and wheel-assembly audit."""
import bpy, math


def body_errors(scene, car, contacts):
    if car.get('vehicle_variant') != 'graphite':
        return [], []
    errors, rows = [], []
    body=bpy.data.objects.get('SprungBody_contact_response')
    if body is None:
        return [{'frame':0,'check':'BODY_RESPONSE_MISSING','value':None}], []
    first_contact=next((r['frame'] for r in contacts if r['contact_gap_m'] is not None and r['contact_gap_m']<=.03),None)
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
        rows.append({'frame':frame,'body_angle_degrees':round(magnitude,5),'heave_m':round(heave,6),'angle_step_degrees':round(step,5)})
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
