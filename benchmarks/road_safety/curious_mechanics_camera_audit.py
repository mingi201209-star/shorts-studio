"""Reproduce shard camera rounding without rendering; candidate fix is memory-only."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess

ANCHOR = '            car.rotation_euler[2]=math.pi/2+module.lane_return_heading(middle)'
STOP = "        visible_car=[ob for ob in car.children_recursive"

def instrument(source, candidate):
    assert source.count(ANCHOR) == source.count(STOP) == 1
    if candidate:
        source = source.replace(ANCHOR, ANCHOR + '\n            for pivot,radius in pivots:\n                pivot.rotation_euler[0]=(centre_x-module.travel_x(1))/(.85*radius)')
    source = source.replace(STOP, '        print("CAMERA_AUDIT_RESULT",json.dumps(camera_proofs),flush=True)\n        return\n' + STOP)
    ast.parse(source)
    return source

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--source',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    renderer=Path(__file__).with_name('render_curious_mechanics.py').resolve()
    wrapper=a.out/'probe.py'
    # Source inputs and on-disk renderer remain untouched. Exit before projection/render.
    wrapper.write_text('import os,sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path.cwd()))\nfrom benchmarks.road_safety.curious_mechanics_camera_audit import instrument\np=Path('+repr(str(renderer))+')\ncode=instrument(p.read_text(),os.environ["CAMERA_AUDIT_CANDIDATE"]=="1")\nexec(compile(code,str(p),"exec"),{"__file__":str(p),"__name__":"__main__"})\n')
    results={}
    for variant,starts in [('A',[121,211]),('C',[181,211])]:
        results[variant]={}
        for candidate in (False,True):
            values=[]
            for start in starts:
                env=dict(os.environ,PYTHONPATH=str(Path.cwd()),CAMERA_AUDIT_CANDIDATE=str(int(candidate)))
                result=subprocess.run(['xvfb-run','-a',a.blender,'-b','-t','4','--python-exit-code','1','-P',str(wrapper),'--','--source',a.source,'--manifest',f'examples/experiments/curious-mechanics-{variant}.json','--start',str(start),'--end',str(start),'--out',str(a.out/f'{variant}-{start}-{int(candidate)}')],env=env,text=True,capture_output=True)
                (a.out/f'{variant}-{start}-{int(candidate)}.log').write_text(result.stdout+'\n'+result.stderr)
                if result.returncode:raise RuntimeError(f'Camera audit process failed: {result.returncode}; inspect saved log')
                lines=[line.partition('CAMERA_AUDIT_RESULT ')[2] for line in result.stdout.splitlines() if line.startswith('CAMERA_AUDIT_RESULT ')]
                assert len(lines)==1, 'Missing camera evidence'
                values.append(json.loads(lines[0]))
            results[variant]['candidate' if candidate else 'original']=values
            print(variant,'candidate' if candidate else 'original',json.dumps(values),flush=True)
    for variant,d in results.items():
        assert d['original'][0]!=d['original'][1], ('Original mismatch not reproduced',variant)
        assert d['candidate'][0]==d['candidate'][1], ('Candidate camera still depends on shard start',variant)
    assert not list(a.out.rglob('frame_*.png')), 'Audit unexpectedly rendered images'
    (a.out/'camera-audit.json').write_text(json.dumps(dict(status='PASS_REPRODUCED_AND_CANDIDATE_EXACT',production_renderer_modified=False,native_frames_rendered=0,results=results),indent=2)+'\n')
    print('CAMERA_AUDIT_PASS_NO_RENDER',flush=True)

if __name__=='__main__':main()
