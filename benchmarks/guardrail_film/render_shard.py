"""Native 1080p Cycles footage from the independently audited scene; no upscaling."""
import bpy, os, json, math, hashlib, struct, subprocess
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parent
film=json.loads((ROOT/'film.json').read_text())
s=bpy.context.scene;cam=s.camera
out=Path(os.environ['FILM_OUT']);out.mkdir(parents=True,exist_ok=True)
start=int(os.environ['FILM_START']);end=int(os.environ['FILM_END'])
assert 91<=start<=end<=900
s.render.resolution_x=1080;s.render.resolution_y=1920;s.render.resolution_percentage=100
s.cycles.samples=32;s.cycles.use_denoising=True;s.render.use_persistent_data=True
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB'
car=bpy.data.objects['CC0 detailed sedan animated as a rigid car']
parts=[o for o in car.children_recursive if o.type=='MESH']
original_visibility={o.name:o.hide_render for o in parts}
hero=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.lens)

def car_bounds():
    points=[o.matrix_world@Vector(p) for o in parts for p in o.bound_box]
    lo=tuple(min(p[k] for p in points) for k in range(3))
    hi=tuple(max(p[k] for p in points) for k in range(3))
    return [Vector((x,y,z)) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]

def set_frame(f):
    n=math.floor(f);s.frame_set(n,subframe=f-n);bpy.context.view_layer.update()

def aim(loc,target,lens):
    cam.location=Vector(loc);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='PERSP';cam.data.lens=lens;cam.data.sensor_fit='VERTICAL'

# Fixed camera per shot, fitted to all car poses in that shot. Mechanical
# inserts intentionally crop the continuous rail and omit the car for visibility.
views={}
for shot in film['shots'][1:]:
    v=shot['view'];a,b=shot['source']
    if v in ('structure','supports'):continue
    points=[]
    for i in range(21):
        set_frame(a+(b-a)*i/20)
        points.extend(car_bounds())
    lo=Vector(tuple(min(p[k] for p in points) for k in range(3)))
    hi=Vector(tuple(max(p[k] for p in points) for k in range(3)))
    target=(lo+hi)/2;target.z=.55
    # Keep the rail contact strip inside the shot, too.
    points.extend(Vector((x,1.7,z)) for x in (lo.x,hi.x) for z in (.2,.9))
    direction={'contact':Vector((.85,-.6,.72)), 'redirect':Vector((.15,-.45,1.2)), 'closing':Vector((1,-.8,.7))}[v].normalized()
    distance=8.
    while True:
        aim(target+direction*distance,target,30)
        bpy.context.view_layer.update()
        projected=[world_to_camera_view(s,cam,p) for p in points]
        if all(.08<=p.x<=.92 and .24<=p.y<=.76 and p.z>0 for p in projected):break
        distance*=1.04
        assert distance<70,('CAMERA_FIT_FAILED',v)
    views[v]=(cam.location.copy(),target.copy(),30)

records=[]
for frame in range(start,end+1):
    shot=next(q for q in film['shots'] if q['start']<=frame<=q['end'])
    t=(frame-shot['start'])/(shot['end']-shot['start']);a,b=shot['source'];source=a+(b-a)*t
    set_frame(source);v=shot['view']
    hidden=v in ('structure','supports')
    for o in parts:o.hide_render=hidden or original_visibility[o.name]
    if v=='structure':
        angle=math.radians(-10+20*t)
        centre=Vector((-.8,1,.62));offset=Vector((-1.1,-3.4,1.5))
        x=offset.x*math.cos(angle)-offset.y*math.sin(angle);y=offset.x*math.sin(angle)+offset.y*math.cos(angle)
        aim(centre+Vector((x,y,offset.z)),centre,36)
    elif v=='supports':
        # View the road-facing post connection from its rear, with an actual
        # deformation replay. The car is omitted as an explanatory cutaway.
        centre=Vector((-.5,1.1,.52));aim((2.1+ .25*t,4.4,1.6),centre,33)
    else:
        loc,target,lens=views[v];aim(loc,target,lens)
    bpy.context.view_layer.update()
    if not hidden:
        projected=[world_to_camera_view(s,cam,p) for p in car_bounds()]
        assert all(.05<=p.x<=.95 and .2<=p.y<=.8 and p.z>0 for p in projected),('FILM_CAR_CROPPED',frame)
    if os.environ.get('FILM_CHECK_ONLY')=='1':continue
    p=out/f'frame_{frame:04d}.png';s.render.filepath=str(p)
    bpy.ops.render.render(write_still=True)
    raw=p.read_bytes();assert raw[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',raw[16:24])==(1080,1920)
    records.append({'frame':frame,'shot':shot['id'],'source_frame':round(source,6),'sha256':hashlib.sha256(raw).hexdigest(),'width':1080,'height':1920,'samples':32})
    if frame==shot['start'] or frame==shot['end'] or frame==(shot['start']+shot['end'])//2:
        import shutil
        shutil.copyfile(p,out/f'review_{frame:04d}.png')
if os.environ.get('FILM_CHECK_ONLY')=='1':
    print('ALL_FILM_CAMERA_FRAMES_PASS',start,end,flush=True)
    raise SystemExit(0)
(out/f'shard_{start:04d}.json').write_text(json.dumps({'scene_sha':film['scene_sha'],'frames':records},indent=2))
subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-framerate','30','-start_number',str(start),'-i',str(out/'frame_%04d.png'),'-frames:v',str(end-start+1),'-c:v','libx264','-preset','slow','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(out/f'chunk_{start:04d}.mp4')],check=True)
print('NATIVE_FILM_SHARD_COMPLETE',start,end,flush=True)
