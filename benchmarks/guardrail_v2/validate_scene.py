
import bpy,json,math,os
from pathlib import Path
from mathutils import Vector
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
def pos_rail(frame,index):
 scene.frame_set(frame)
 vl=rail.data.shape_keys.key_blocks
 v0=vl[0].data[index].co
 v1=vl[1].data[index].co
 val=vl[1].value
 xyz=v0.lerp(v1,val)
 return rail.matrix_world @ xyz
def screen(p):
 v=world_to_camera_view(scene,cam,p)
 return {'x':round(float(v.x)*width,2),'y':round((1-float(v.y))*height,2),'depth':round(float(v.z),3)}
NX=88;NZ=24
i=min(range(NX),key=lambda k:abs(-7.1+(14.2*k/(NX-1))))
idx=i*NZ+int(NZ*.5)
screen_base=screen(pos_rail(1,idx))
screen_peak=screen(pos_rail(40,idx))
delta=math.hypot(screen_base['x']-screen_peak['x'],screen_base['y']-screen_peak['y'])
scene.frame_set(1)
car_coords=[car.matrix_world@Vector(c) for c in [(-1,-1,0),(1,1,1.5)]]
car_range=[screen(x) for x in car_coords]
out={'scene':'Guardrail V2 local isolated development','quality_gate':'UNASSESSED','camera_static':True,'native_resolution':[width,height],'samples':scene.cycles.samples,'frame1':screen_base,'frame40':screen_peak,'projected_delta_px':round(delta,2),'rail_vertex_index':idx,'car_world_project_sample':car_range,'has_reference_guide':bool(guide),'editorial_flag':'CONCEPTUAL animation, NOT crash-test validated'}
d.joinpath('v2_validation.json').write_text(json.dumps(out,indent=2))
print('RENDER_QA_REPORT',json.dumps(out),flush=True)
assert delta>=40,'insufficient visible rail displacement'
assert scene.cycles.samples>=16
assert screen_base['depth']>0 and screen_peak['depth']>0
assert 20<=screen_peak['x']<=1060 and 100<=screen_peak['y']<=1810,(screen_peak,delta)
print('V2_SCENE_GEOMETRY_QA_PASS',flush=True)

