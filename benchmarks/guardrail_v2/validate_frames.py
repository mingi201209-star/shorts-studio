"""Validate all rendered PNG dimensions and hashes, including the original 1/22/40 proofs."""
import os,json,struct,hashlib
from pathlib import Path
d=Path(os.environ['VISUAL_V2_OUTPUT'])
paths=[d/f'frame_{i:04d}.png' for i in range(1,91)]
records=[]
for p in paths:
 b=p.read_bytes()
 assert b[:8]==b'\x89PNG\r\n\x1a\n'
 assert struct.unpack('>II',b[16:24])==(1080,1920),p
 records.append({'frame':int(p.stem.split('_')[1]),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
assert len({r['sha256'] for r in records})==90,'Frozen/duplicate frame'
(d/'frame_validation.json').write_text(json.dumps({'status':'PASS','frames':records,'native_resolution':[1080,1920],'editorial_quality':'UNASSESSED'},indent=2))
print('NATIVE_SEQUENCE_PASS',len(records))
