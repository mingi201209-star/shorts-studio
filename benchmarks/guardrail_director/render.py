"""Fixed-camera native director candidate; no object/physics/TTS changes."""
import bpy,os,json,math,hashlib,struct,time,subprocess
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parent
film=json.loads((ROOT/'film.json').read_text());s=bpy.context.scene;cam=s.camera
out=Path(os.environ['FILM_OUT']);out.mkdir(parents=True,exist_ok=True)
s.render.resolution_x=1080;s.render.resolution_y=1920;s.render.resolution_percentage=100
engine=os.environ.get('DIRECTOR_ENGINE','CYCLES')
assert engine in ('BLENDER_EEVEE','CYCLES')
s.render.engine=engine
if engine=='BLENDER_EEVEE':
    s.eevee.taa_render_samples=64;s.eevee.taa_samples=64
else:
    s.cycles.samples=32;s.cycles.use_denoising=True
s.render.use_persistent_data=True
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB'
car=bpy.data.objects['CC0 detailed sedan animated as a rigid car']
parts=[o for o in car.children_recursive if o.type=='MESH']
visibility={o.name:o.hide_render for o in parts}
audit_path=Path(os.environ['DIRECTOR_SOURCE_AUDIT'])
audit=json.loads(audit_path.read_text())
assert audit['status']=='PASS' and audit['frames_checked']==90 and not audit['errors']
assert len(parts)==audit['mesh_parts']
def set_frame(value):
    f=math.floor(value);s.frame_set(f,subframe=value-f);bpy.context.view_layer.update()
def bounds():
    pts=[o.matrix_world@Vector(p) for o in parts for p in o.bound_box]
    lo=Vector(tuple(min(p[k] for p in pts) for k in range(3)))
    hi=Vector(tuple(max(p[k] for p in pts) for k in range(3)))
    return [Vector((x,y,z)) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)]
def aim(loc,target,lens):
    cam.location=Vector(loc);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='PERSP';cam.data.lens=lens;cam.data.sensor_fit='VERTICAL'
views={}
detail_rois={}
for shot in film['shots']:
    v=shot['view'];a,b=shot['source']
    if v=='structure':
        views[v]=(Vector((1.6,-2.5,1.75)),Vector((-.6,.9,.55)),36);continue
    if v=='supports':
        views[v]=(Vector((1.8,3.8,1.65)),Vector((-.5,1.0,.44)),36);continue
    if v=='contact':
        # A genuine 3D contact insert, not a crop/zoom of the earlier image.
        witnesses=[Vector(row['contact_witness']['car_point_m']) for row in audit['frames']
                   if a<=row['frame']<=b and row.get('contact_witness')]
        assert witnesses, 'NO_CONTACT_WITNESSES'
        pts=[p+Vector((dx,dy,dz)) for p in witnesses for dx in (-.4,.4)
             for dy in (-.22,.22) for dz in (-.28,.48)]
        detail_rois[v]=pts
    else:
        pts=[]
    if v!='contact':
        for n in range(21):
            set_frame(a+(b-a)*n/20);pts+=bounds()
    lo=Vector(tuple(min(p[k] for p in pts) for k in range(3)))
    hi=Vector(tuple(max(p[k] for p in pts) for k in range(3)))
    target=(lo+hi)/2
    if v!='contact':target.z=.58
    # View impact from the rail/shoulder side, so contact is not hidden behind the car.
    direction={'hero':Vector((1.0,.45,.42)),'contact':Vector((1.0,.65,.48)),
               'redirect':Vector((.15,-.4,1.15)),'closing':Vector((1,-.8,.7))}[v].normalized()
    distance=4.
    for _ in range(100):
        aim(target+direction*distance,target,36);bpy.context.view_layer.update()
        projected=[world_to_camera_view(s,cam,p) for p in pts]
        if all(.07<=p.x<=.93 and .20<=p.y<=.90 and p.z>0 for p in projected):break
        distance*=1.04
    else:raise AssertionError(('FIXED_CAMERA_FIT_FAILED',v))
    views[v]=(cam.location.copy(),target.copy(),36)
frames=[int(x) for x in os.environ.get('DIRECTOR_FRAMES','').split(',') if x]
if not frames:frames=list(range(int(os.environ['FILM_START']),int(os.environ['FILM_END'])+1))
records=[];camera_by_shot={}
for frame in frames:
    shot=next(q for q in film['shots'] if q['start']<=frame<=q['end'])
    t=(frame-shot['start'])/(shot['end']-shot['start']);a,b=shot['source'];source=a+(b-a)*t
    set_frame(source);v=shot['view'];hidden=v in ('structure','supports')
    for ob in parts:ob.hide_render=hidden or visibility[ob.name]
    loc,target,lens=views[v];aim(loc,target,lens);bpy.context.view_layer.update()
    camera=[round(x,7) for row in cam.matrix_world for x in row]+[cam.data.lens]
    if shot['id'] in camera_by_shot:assert camera_by_shot[shot['id']]==camera,'CAMERA_MOVED_WITHIN_SHOT'
    camera_by_shot[shot['id']]=camera
    footprint=None
    if not hidden:
        projected=[world_to_camera_view(s,cam,p) for p in bounds()]
        if v!='contact':
            assert all(.045<=p.x<=.955 and .18<=p.y<=.92 and p.z>0 for p in projected),('CAR_CROPPED',frame)
        else:
            roi=[world_to_camera_view(s,cam,p) for p in detail_rois[v]]
            assert all(.045<=p.x<=.955 and .18<=p.y<=.92 and p.z>0 for p in roi),('CONTACT_ROI_CROPPED',frame)
        footprint=[min(p.x for p in projected),max(p.x for p in projected),min(p.y for p in projected),max(p.y for p in projected)]
    witness=audit['frames'][min(89,max(0,round(source)-1))].get('contact_witness')
    contact=None
    if witness and not hidden:
        p=world_to_camera_view(s,cam,Vector(witness['car_point_m']))
        contact=[p.x,p.y,p.z]
        assert .04<p.x<.96 and .18<p.y<.92 and p.z>0,('CONTACT_OUT_OF_FRAME',frame)
    if os.environ.get('FILM_CHECK_ONLY')=='1':continue
    path=out/f'frame_{frame:04d}.png';s.render.filepath=str(path)
    begin=time.monotonic();bpy.ops.render.render(write_still=True);elapsed=time.monotonic()-begin
    data=path.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',data[16:24])==(1080,1920)
    records.append({'frame':frame,'shot':shot['id'],'source_frame':round(source,6),'sha256':hashlib.sha256(data).hexdigest(),'width':1080,'height':1920,'samples':64 if engine=='BLENDER_EEVEE' else 32,'renderer':engine,'camera':camera,'car_bounds':footprint,'contact_projection':contact,'framing':shot.get('framing','full_subject'),'render_seconds':round(elapsed,3)})
    print('NATIVE_DIRECTOR_FRAME',frame,'seconds',round(elapsed,3),flush=True)
if os.environ.get('FILM_CHECK_ONLY')=='1':
    print('FIXED_CAMERA_AND_CONTACT_AUDIT_PASS',len(frames),flush=True);raise SystemExit(0)
(out/f"shard_{frames[0]:04d}.json").write_text(json.dumps({'scene_sha':film['scene_sha'],'source_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(),'physical_validation':False,'frames':records},indent=2))
if not os.environ.get('DIRECTOR_FRAMES'):
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-framerate','30','-start_number',str(frames[0]),'-i',str(out/'frame_%04d.png'),'-frames:v',str(len(frames)),'-c:v','libx264','-preset','slow','-crf','17','-pix_fmt','yuv420p',str(out/f'chunk_{frames[0]:04d}.mp4')],check=True)
