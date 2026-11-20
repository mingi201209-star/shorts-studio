"""Resumable local native render queue. No upload, paid APIs or editorial approval."""
import argparse,hashlib,json,os,subprocess,sys,time,fcntl
from PIL import Image
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from shorts_studio.factory.curious_mechanics_native_qa import verify
from shorts_studio.factory.curious_mechanics_timeline import load_episode,detail_stage
ROOT=Path(__file__).resolve().parents[2]
RENDERER=ROOT/'benchmarks/road_safety/render_curious_mechanics.py'

def write(path,data):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def run(a):
 a.out.mkdir(parents=True,exist_ok=True)
 lock=(a.out.parent/'curious-mechanics-render.lock').open('a')
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if head!=a.expected_head:raise ValueError('Wrong worktree head')
 paths=[RENDERER,Path(__file__),ROOT/'shorts_studio/factory/curious_mechanics_timeline.py',ROOT/'shorts_studio/factory/rumble_episode2.py',ROOT/'shorts_studio/factory/curious_mechanics_native_qa.py',ROOT/'examples/experiments/curious-mechanics-rumble-formats.json']+[ROOT/f'examples/experiments/curious-mechanics-{v}.json' for v in 'ABC']
 hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
 def stable():
  if any(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=digest for p,digest in hashes.items()):raise ValueError('Queue inputs changed')
 receipt=a.out/'queue-state.json';state=dict(head=head,input_hashes=hashes,last_frame=a.last_frame,status='RUNNING',complete_shards=[],videos_completed=0,editorial='HOLD_UNREVIEWED',upload_authorized=False)
 write(receipt,state)
 try:
  for v in 'ABC':
   manifest=ROOT/f'examples/experiments/curious-mechanics-{v}.json';episode=load_episode(manifest)
   spans=[(n,min(n+29,a.last_frame)) for n in range(1,a.last_frame+1,30)]
   if a.last_frame==90:
    contact=next(s for s in episode['shots'] if detail_stage(s['id'])=='rolling_contact' and s['start']>150)
    contact_start=((contact['start']-1+29)//30)*30+1
    if contact_start+29>contact['end']:raise ValueError('No complete contact shard')
    spans.append((contact_start,contact_start+29))
   for start,end in spans:
    stable();folder=a.out/v/f'{start:04}-{end:04}';folder.mkdir(parents=True,exist_ok=True)
    state.update(variant=v,start=start,end=end,updated_at=time.time());write(receipt,state)
    proof=folder/'episode-proof.json'
    if not proof.exists():
     if any(folder.glob('frame_*.png')):raise ValueError('Incomplete prior shard; preserve and explicitly reconcile before rerender')
     with (folder/'render.log').open('w') as log:
      subprocess.run([str(a.blender),'-b','-t','4','--python-exit-code','1','-P',str(RENDERER),'--','--source',str(a.source),'--manifest',str(manifest),'--start',str(start),'--end',str(end),'--out',str(folder)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    stable();qa=verify(folder,manifest,RENDERER);write(folder/'native-validation.json',qa)
    clip=folder/'native-lossless.mkv'
    if not clip.exists():
     subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-start_number',str(start),'-i',str(folder/'frame_%04d.png'),'-frames:v',str(end-start+1),'-c:v','ffv1','-level','3','-pix_fmt','rgb24',str(clip)],check=True)
    decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(clip),'-pix_fmt','rgb24','-f','framemd5','-'],text=True)
    actual=[line.split(',')[-1].strip() for line in decoded.splitlines() if line and not line.startswith('#')]
    expected=[]
    for frame in range(start,end+1):
     with Image.open(folder/f'frame_{frame:04d}.png') as picture: expected.append(hashlib.md5(picture.convert('RGB').tobytes()).hexdigest())
    if actual!=expected:raise ValueError('Lossless clip differs from original native frames')
    state['complete_shards'].append(dict(variant=v,start=start,end=end,native_qa=qa['status'],clip_sha256=hashlib.sha256(clip.read_bytes()).hexdigest()));write(receipt,state)
    print(v,start,end,'PASS_NATIVE_ORIGINAL_SHARD',flush=True)
  state.update(status='NATIVE_PROOFS_READY_REVIEW_REQUIRED' if a.last_frame==90 else 'NATIVE_FRAMES_READY_ASSEMBLY_REQUIRED',completed_at=time.time());write(receipt,state)
 except Exception as exc:
  state.update(status='HOLD_FAILED',error=f'{type(exc).__name__}: {exc}',failed_at=time.time());write(receipt,state);raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--blender',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-head',required=True);p.add_argument('--last-frame',type=int,choices=[90,900],default=90);run(p.parse_args())
