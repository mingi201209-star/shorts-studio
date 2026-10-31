"""Assemble newly rendered progressive PNG shards on GitHub, preserving audio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import Image
from benchmarks.road_safety import episode2_film as film
from benchmarks.road_safety import curious_mechanics_delivery as delivery
from benchmarks.road_safety import curious_mechanics_fast_batch as fast
from shorts_studio.factory import curious_mechanics_timeline as timeline
from shorts_studio.factory.curious_mechanics_native_qa import verify


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble(root, source, variant, out):
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'GitHub-only encoding'
    out.mkdir(parents=True, exist_ok=False)
    manifest = delivery.ROOT / f'examples/experiments/curious-mechanics-progressive-{variant}.json'
    episode = timeline.load_episode(manifest)
    roles = ['_'.join(s['id'].split('_')[2:]) for s in episode['shots']]
    assert tuple(roles) == timeline.PROGRESSIVE_STYLES
    assert len(roles) == len(set(roles)) == 5, 'Native visual role returned'
    selected = []
    for proof_path in root.rglob('episode-proof.json'):
        proof = json.loads(proof_path.read_text())
        if proof['episode_id'] != 'curious-mechanics-' + variant:
            continue
        folder = proof_path.parent
        qa = verify(folder, manifest, delivery.ROOT/'benchmarks/road_safety/render_curious_mechanics.py')
        receipt = json.loads((folder/'native-validation.json').read_text())
        clip = folder/'native-lossless.mkv'
        assert receipt['decoded_exact'] and receipt['clip_sha256'] == digest(clip)
        decoded = film.run(['ffmpeg','-v','error','-i',clip,'-pix_fmt','rgb24','-f','framemd5','-']).stdout
        actual = [x.split(',')[-1].strip() for x in decoded.splitlines() if x and not x.startswith('#')]
        expected = []
        for n in proof['frame_numbers']:
            with Image.open(folder/f'frame_{n:04d}.png') as im:
                expected.append(hashlib.md5(im.convert('RGB').tobytes()).hexdigest())
        assert actual == expected, 'Lossless/native pixel mismatch'
        selected.append((proof, clip, expected, qa))
    selected.sort(key=lambda s:s[0]['first_frame'])
    film.validate_shard_layout([x[0] for x in selected])
    pixels = [h for s in selected for h in s[2]]
    assert len(pixels) == len(set(pixels)) == 900
    cameras = {}
    for proof, _, _, _ in selected:
        for name, camera in proof['camera_by_shot'].items():
            assert name not in cameras or cameras[name] == camera, 'Camera reset between shards'
            cameras[name] = camera
    assert set(cameras) == {s['id'] for s in episode['shots']}
    prior = json.loads((source/'revision-validation.json').read_text())
    assert prior['technical_status'] == 'PASS'
    previous = source/f'curious-mechanics-{variant}-mechanism-v2.mp4'
    assert digest(previous) == prior['sha256']
    audio = json.loads((source/'audio/audio-validation.json').read_text())
    assert audio['status'] == 'PASS' and audio['voice'] == 'en-US-AndrewNeural' and audio['rate'] == '+5%'
    assert digest(source/'audio/narration.wav') == audio['narration_sha256'] == json.loads(manifest.read_text())['measured_audio_sha256']
    for name in ['film.ass','narration.wav','audio-validation.json']:
        shutil.copyfile(source/'audio'/name,out/name)
    # Keep the existing labelled diagram, but hide it over the new body interval.
    diagram = fast.schematic(variant, out, audio['beats'], source_episode=episode)
    concat = out/'concat.txt'
    concat.write_text(''.join("file '"+str(clip.resolve())+"'\n" for _,clip,_,_ in selected))
    final = out/f'curious-mechanics-{variant}-progressive-v3.mp4'
    film.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',concat,'-i',out/'narration.wav',
              '-vf',f'ass={diagram},'+film.caption_filter(out),'-map','0:v:0','-map','1:a:0',
              '-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p',
              '-c:a','aac','-b:a','192k','-movflags','+faststart',final])
    info = film.probe(final)
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    au = next(s for s in info['streams'] if s['codec_type']=='audio')
    assert (video['width'],video['height'],video['r_frame_rate'],int(video['nb_read_frames'])) == (1080,1920,'30/1',900)
    assert au['codec_name']=='aac' and au['sample_rate']=='48000' and au['channels']==1
    assert abs(float(info['format']['duration'])-30)<.04
    film.run(['ffmpeg','-v','error','-i',final,'-f','null','-'])
    hashes = film.run(['ffmpeg','-v','error','-i',final,'-map','0:v:0','-f','framemd5','-']).stdout
    unique = [x.split(',')[-1].strip() for x in hashes.splitlines() if x and not x.startswith('#')]
    assert len(unique)==len(set(unique))==900
    assert 'black_start:' not in film.run(['ffmpeg','-hide_banner','-i',final,'-vf','blackdetect=d=0.15:pix_th=0.06','-an','-f','null','-']).stderr
    gaps=film.silence(final)
    levels=film.check_loudness(film.loudness(final))
    viewer=film.original_video_qa(final,out,audio['cues'])
    meaning=delivery.semantic(final,out,episode,audio)
    report=dict(technical_status='PASS',sha256=digest(final),source_frames_verified=900,
                frames=900,seconds=30,resolution=[1080,1920],cycles_samples=32,
                native_roles=roles,native_role_returns=0,shots=episode['shots'],
                camera_by_shot=cameras,manifest_sha256=digest(manifest),
                audio_validation=audio,previous_revision_sha256=prior['sha256'],
                native_source_shards=[dict(first=s[0]['first_frame'],last=s[0]['last_frame'],
                    clip_sha256=digest(s[1]),renderer_sha256=s[0]['renderer_source_sha256'],
                    timeline_sha256=s[0]['timeline_source_sha256']) for s in selected],
                original_video_qa=viewer,semantic_visual_qa=meaning,
                silence_seconds=gaps,loudness=levels,editorial_status='HOLD_ACTUAL_REVIEW',
                human_first_view='UNVERIFIED',upload_authorized=False)
    (out/'film-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PROGRESSIVE_FILM_PASS',variant,report['sha256'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--variant',choices=list('ABC'),required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assemble(a.native,a.source,a.variant,a.out)
