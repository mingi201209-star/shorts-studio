"""Bounded, contact-triggered sprung-body illustration, not calibrated crash physics."""
import bpy, math
from mathutils import Matrix, Vector, Euler

CENTRE = Vector((0, 0, .45))


def response(frame, onset):
    t = frame-onset
    if t <= 0:
        return (0., 0., 0.)
    def smooth(x):
        x=max(0.,min(1.,x)); return x*x*(3-2*x)
    load=smooth(t/10)*(1-smooth((frame-48)/24))
    roll=math.radians(1.8)*load+math.radians(.6)*math.exp(-t/14)*math.sin(t*.6)
    pitch=math.radians(.55)*math.exp(-t/18)*math.sin(t*.45)
    heave=-.012*load
    return pitch,roll,heave


def local_matrix(frame, onset):
    pitch,roll,heave=response(frame,onset)
    return (Matrix.Translation(CENTRE+Vector((0,0,heave)))
            @Euler((pitch,roll,0),'XYZ').to_matrix().to_4x4()
            @Matrix.Translation(-CENTRE))


def attach_body(car, wheel_pivots, onset, frames):
    excluded=set(wheel_pivots)
    # Calipers follow the unsprung wheel centres, without spinning with rotors.
    roots=[o for o in car.children if o not in excluded and not o.name.startswith('Brake caliper')]
    bpy.ops.object.empty_add(type='PLAIN_AXES')
    body=bpy.context.object;body.name='SprungBody_contact_response';body.parent=car
    body.location=CENTRE
    for ob in roots:
        old=ob.matrix_local.copy();ob.parent=body;ob.matrix_parent_inverse.identity()
        ob.matrix_basis=Matrix.Translation(-CENTRE)@old
    body.rotation_mode='XYZ'
    for frame in range(1,frames+1):
        pitch,roll,heave=response(frame,onset)
        body.location=CENTRE+Vector((0,0,heave));body.rotation_euler=(pitch,roll,0)
        body.keyframe_insert('location',frame=frame)
        body.keyframe_insert('rotation_euler',frame=frame)
    car['body_response_onset']=onset
    car['body_response_style']='bounded contact-triggered sprung-body illustration'
    return body
