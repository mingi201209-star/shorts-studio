import json,os
from pathlib import Path
d=Path(os.environ['VISUAL_V2_OUTPUT'])
r=json.loads((d/'ffprobe.json').read_text())
v=[x for x in r['streams'] if x['codec_type']=='video']
assert len(v)==1
s=v[0]
assert (s['width'],s['height'],s['codec_name'],s['pix_fmt'],s['r_frame_rate'])==(1080,1920,'h264','yuv420p','30/1')
assert int(s['nb_read_frames'])==90
assert abs(float(r['format']['duration'])-3.0)<.04
assert int(r['format']['size'])>10000
(d/'video_validation.json').write_text(json.dumps({'status':'PASS','frames':90,'duration':float(r['format']['duration']),'visual_only':True,'editorial_quality':'UNASSESSED','physical_validation':False},indent=2))
print('NATIVE_VIDEO_INTEGRITY_PASS')
