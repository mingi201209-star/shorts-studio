"""Add a labelled causal schematic to hash-bound native films; GitHub only encodes.

This is an editorial revision batch, never seven distinct topics or a new native
simulation. Existing captions/audio and the entire native picture remain intact.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import episode2_film as film
from benchmarks.road_safety import curious_mechanics_delivery as delivery
from shorts_studio.factory import curious_mechanics_timeline as timeline

HASHES = {
    'A': '3bcbb08bb88ae3979e2e4cfa8fcb7c571d9a5ebb7d0f6c5b1f38b064cbbf8695',
    'B': 'e764fd636e846dc0030ddb2cd9ddd3cf75eb915ad6c779bf9e675f23e3de9578',
    'C': 'de163c423a575673c6beabf7b7805bbd783799ec8cd0232cd4c630ede020546c',
}
HEADERS = {'A': 'ROAD DAMAGE?', 'B': 'WHY THE RUMBLE?', 'C': 'WHAT JUST HAPPENED?'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def polygon(points):
    return 'm ' + ' l '.join(f'{round(x)} {round(y)}' for x, y in points)


def waveform_points(t, groove):
    center=[(x,280+(24*math.sin((x-650)/28+t*math.tau*1.8) if groove else 0))
            for x in range(650,961,4)]
    # Forward top + reversed bottom avoids a self-intersecting filled polygon.
    return [(x,y-3) for x,y in center]+[(x,y+3) for x,y in reversed(center)]


def schematic(variant, out):
    """A separate drawing, not a measurement or alteration of source geometry."""
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Diagram,DejaVu Sans,38,&H00FFFFFF,&H00FFFFFF,&H001B1510,&H001B1510,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = []

    def event(start, end, text, layer=2):
        lines.append(f'Dialogue: {layer},{film.stamp(start)},{film.stamp(end)},Diagram,,0,0,0,,{text}\n')

    def shape(start, end, points, color, layer=1):
        event(start, end, r'{\an7\pos(0,0)\p1\1c&H' + color + '&}' + polygon(points), layer)

    def label(start, end, x, y, text, size=38):
        event(start, end, r'{\an7\pos(' + f'{x},{y}' + r')\fs' + str(size) + '}' + text)

    # Source proof bounds establish every required car/wheel pixel below y=460.
    # Keep a 20px gap: drawing occupies y=70..440 only, captions below y=1440.
    shape(0, 30, [(70,70),(1010,70),(1010,440),(70,440)], '201810', 0)
    label(0, 2, 110, 92, HEADERS[variant], 48)
    label(2, 7.7, 110, 92, 'CUTS BELOW THE SURFACE', 42)
    label(7.7, 13.4, 110, 92, 'REPEATED CONTACT = VIBRATION', 38)
    label(13.4, 26, 110, 92, 'SOUND + SHAKE = A WARNING', 40)
    label(26, 30, 110, 92, 'A WARNING. NOT AUTO-STEERING.', 38)
    label(0, 26, 110, 393, 'SCHEMATIC / MOTION EXAGGERATED', 25)
    label(26, 30, 110, 393, 'ILLUSTRATION / DRIVER RESPONSE REQUIRED', 23)
    for frame in range(900):
        t = frame / 30
        end = (frame + 1) / 30
        # No suggested calibrated force values or invented source measurements.
        phase = (t * 1.8) % 1
        groove = t >= 1
        drop = 22 * max(0, math.cos(phase * math.tau)) if groove else 0
        road = [(110,310)]
        for x in range(110, 571, 4):
            local = ((x - 300) / 160 + phase) % 1
            depth = 22 * max(0, math.cos(local * math.tau)) if groove else 0
            road.append((x,310 + depth))
        road += [(570,365),(110,365)]
        shape(t,end,road,'88766B')
        cy=253+drop
        shape(t,end,[(300+56*math.cos(i*math.tau/48),cy+56*math.sin(i*math.tau/48)) for i in range(49)],'E8DFCF')
        shape(t,end,[(300+32*math.cos(i*math.tau/32),cy+32*math.sin(i*math.tau/32)) for i in range(33)],'45382B')
        angle=-t*(160*1.8/56)
        shape(t,end,[(297,cy-3),(300+28*math.cos(angle),cy+28*math.sin(angle)),(303,cy+3)],'F6C853')
        label(t,end,648,185,'SMOOTH' if not groove else 'CONTACT CHANGES',29)
        # Graph is explicitly illustrative. Native picture below is never warped.
        shape(t,end,waveform_points(t,groove),'F6C853')
        label(t,end,650,330,'QUIET / STEADY' if not groove else 'SOUND + VIBRATION',25)
    path=out/'mechanism.ass'
    path.write_text(header+''.join(lines))
    return path


def build(source, variant, out):
    assert os.environ.get('GITHUB_ACTIONS')=='true', 'Encoding is GitHub-only'
    start=time.monotonic()
    out.mkdir(parents=True,exist_ok=False)
    native=source/f'curious-mechanics-{variant}.mp4'
    prior=json.loads((source/'film-validation.json').read_text())
    assert digest(native)==HASHES[variant]==prior['sha256']
    assert prior['technical_status']=='PASS' and prior['source_frames_verified']==900
    audio=json.loads((source/'audio-validation.json').read_text())
    assert audio['voice']=='en-US-AndrewNeural' and audio['rate']=='+5%' and audio['status']=='PASS'
    ass=schematic(variant,out)
    final=out/f'curious-mechanics-{variant}-mechanism-v2.mp4'
    film.run(['ffmpeg','-v','error','-i',native,'-vf',f'ass={ass}',
              '-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p',
              '-c:a','copy','-movflags','+faststart',final])
    info=film.probe(final)
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_read_frames']))==(1080,1920,'30/1',900)
    assert abs(float(info['format']['duration'])-30)<.04
    film.run(['ffmpeg','-v','error','-i',final,'-f','null','-'])
    # Prove unchanged sound by decoded PCM, not merely by its codec label.
    pcm=lambda p:film.run(['ffmpeg','-v','error','-i',p,'-map','0:a:0','-f','md5','-']).stdout
    assert pcm(native)==pcm(final),'AUDIO_CHANGED'
    md5=film.run(['ffmpeg','-v','error','-i',final,'-map','0:v:0','-f','framemd5','-']).stdout
    frames=[s.split(',')[-1].strip() for s in md5.splitlines() if s and not s.startswith('#')]
    assert len(frames)==len(set(frames))==900
    assert 'black_start:' not in film.run(['ffmpeg','-hide_banner','-i',final,'-vf','blackdetect=d=0.15:pix_th=0.06','-an','-f','null','-']).stderr
    levels=film.check_loudness(film.loudness(final));gaps=film.silence(final)
    viewer=film.original_video_qa(final,out,audio['cues'])
    episode={'shots':[]}
    for s in prior['semantic_visual_qa']:
        n=round(s['timestamp']*30)+1
        episode['shots'].append({'id':s['shot'],'start':n,'end':n})
    semantic=delivery.semantic(final,out,episode,audio)
    report=dict(technical_status='PASS',sha256=digest(final),source_sha256=digest(native),
                source_native_validation=prior,source_is_encoded_native_film=True,
                new_native_render=False,schematic_sha256=digest(ass),audio_pcm_unchanged=True,
                frames=900,seconds=30,resolution=[1080,1920],original_video_qa=viewer,
                semantic_visual_qa=semantic,loudness=levels,silence_seconds=gaps,
                batch_edit_and_qa_seconds=round(time.monotonic()-start,3),
                editorial_status='HOLD_ACTUAL_REVIEW',human_first_view='UNVERIFIED',
                distinct_topic=False,upload_authorized=False)
    (out/'revision-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['technical_status','sha256','batch_edit_and_qa_seconds']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--variant',choices=list('ABC'),required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.source,a.variant,a.out)
