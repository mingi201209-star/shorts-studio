"""Validate native PNGs and an exactly decoded FFV1 artifact; never publish."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from shorts_studio.factory.curious_mechanics_native_qa import verify

def build(out,manifest):
 renderer=Path(__file__).with_name('render_curious_mechanics.py')
 qa=verify(out,manifest,renderer)
 proof=json.loads((out/'episode-proof.json').read_text());nums=proof['frame_numbers']
 clip=out/'native-lossless.mkv'
 subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-start_number',str(nums[0]),'-i',str(out/'frame_%04d.png'),'-frames:v',str(len(nums)),'-c:v','ffv1','-level','3','-pix_fmt','rgb24',str(clip)],check=True)
 decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(clip),'-pix_fmt','rgb24','-f','framemd5','-'],text=True)
 actual=[line.split(',')[-1].strip() for line in decoded.splitlines() if line and not line.startswith('#')]
 expected=[]
 for n in nums:
  with Image.open(out/f'frame_{n:04d}.png') as im:expected.append(hashlib.md5(im.convert('RGB').tobytes()).hexdigest())
 if actual!=expected:raise ValueError('Lossless clip differs from native source')
 qa.update(clip_sha256=hashlib.sha256(clip.read_bytes()).hexdigest(),decoded_exact=True)
 (out/'native-validation.json').write_text(json.dumps(qa,indent=2)+'\n');print(json.dumps(qa),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();build(a.out,a.manifest)
