"""Reproduce shard camera rounding without rendering; candidate fix is memory-only."""
import argparse
import ast
import json
import hashlib
import os
from pathlib import Path
import subprocess

ANCHOR = '            car.rotation_euler[2]=math.pi/2+module.lane_return_heading(middle)'
STOP = "        visible_car=[ob for ob in car.children_recursive"

def instrument(source, candidate, scan=False, check_motion=False):
    assert source.count(ANCHOR) == source.count(STOP) == 1
    if candidate:
        source = source.replace(ANCHOR, ANCHOR + '\n            for pivot,radius in pivots:\n                pivot.rotation_euler[0]=(centre_x-module.travel_x(1))/(.85*radius)')
    if scan:
        end = '    if len({x["sha256"] for x in checksums})!=len(checksums):'
        assert source.count(end) == 1
        motion = '        for pivot,radius in pivots:\n            expected_spin=Vector(((x-module.travel_x(1))/(.85*radius),0,0)).x\n            if pivot.rotation_euler[0]!=expected_spin:raise ValueError(\"Absolute wheel rotation changed\")\n' if check_motion else ''
        source = source.replace(STOP, motion + '        continue\n' + STOP)
        source = source.replace(end, '    print("CAMERA_AUDIT_RESULT",json.dumps(camera_proofs),flush=True)\n    return\n' + end)
    else:
        source = source.replace(STOP, '        print("CAMERA_AUDIT_RESULT",json.dumps(camera_proofs),flush=True)\n        return\n' + STOP)
    ast.parse(source)
    return source

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--source',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--inventory',action='store_true');p.add_argument('--production-fixed',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    renderer=Path(__file__).with_name('render_curious_mechanics.py').resolve()
    wrapper=a.out/'probe.py'
    # Source inputs and on-disk renderer remain untouched. Exit before projection/render.
    wrapper.write_text('import os,sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path.cwd()))\nfrom benchmarks.road_safety.curious_mechanics_camera_audit import instrument\np=Path('+repr(str(renderer))+')\ncode=instrument(p.read_text(),os.environ["CAMERA_AUDIT_CANDIDATE"]=="1",os.environ.get("CAMERA_AUDIT_SCAN")=="1",os.environ.get("CAMERA_AUDIT_PRODUCTION_FIXED")=="1")\nexec(compile(code,str(p),"exec"),{"__file__":str(p),"__name__":"__main__"})\n')
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
        assert (d['original'][0]==d['original'][1]) if a.production_fixed else (d['original'][0]!=d['original'][1]), ('Production equality / original reproduction failed',variant)
        assert d['candidate'][0]==d['candidate'][1], ('Candidate camera still depends on shard start',variant)
    if a.inventory:
        inventory=[];canonical={}
        for variant in 'ABC':
            for start in range(1,901,30):
                env=dict(os.environ,CAMERA_AUDIT_CANDIDATE='0' if a.production_fixed else '1',CAMERA_AUDIT_SCAN='1',CAMERA_AUDIT_PRODUCTION_FIXED=str(int(a.production_fixed)))
                out=a.out/f'inventory-{variant}-{start}'
                result=subprocess.run(['xvfb-run','-a',a.blender,'-b','-t','4','--python-exit-code','1','-P',str(wrapper),'--','--source',a.source,'--manifest',f'examples/experiments/curious-mechanics-{variant}.json','--start',str(start),'--end',str(start+29),'--out',str(out)],env=env,text=True,capture_output=True)
                (a.out/f'inventory-{variant}-{start}.log').write_text(result.stdout+'\n'+result.stderr)
                if result.returncode:raise RuntimeError(f'Inventory process failed: {variant} {start}')
                lines=[line.partition('CAMERA_AUDIT_RESULT ')[2] for line in result.stdout.splitlines() if line.startswith('CAMERA_AUDIT_RESULT ')]
                assert len(lines)==1
                cameras=json.loads(lines[0]);assert cameras
                for shot,camera in cameras.items():
                    assert shot not in canonical or canonical[shot]==camera, ('Candidate camera mismatch',shot,start)
                    canonical[shot]=camera
                inventory.append(dict(variant=variant,start=start,end=start+29,camera_by_shot=cameras))
                print('CAMERA_INVENTORY',variant,start,flush=True)
        assert len(inventory)==90
        (a.out/'camera-inventory.json').write_text(json.dumps(dict(status='PASS_EXACT_CANONICAL_CAMERAS_ALL_90_SHARDS',renderer_source_sha256=hashlib.sha256(renderer.read_bytes()).hexdigest(),candidate_in_memory_only=not a.production_fixed,absolute_wheel_spin_exact=a.production_fixed,native_frames_rendered=0,shards=inventory,camera_by_shot=canonical),indent=2)+'\n')
    assert not list(a.out.rglob('frame_*.png')), 'Audit unexpectedly rendered images'
    (a.out/'camera-audit.json').write_text(json.dumps(dict(status='PASS_PRODUCTION_FIXED_CAMERAS' if a.production_fixed else 'PASS_REPRODUCED_AND_CANDIDATE_EXACT',production_renderer_modified=False,native_frames_rendered=0,results=results),indent=2)+'\n')
    print('CAMERA_AUDIT_PASS_NO_RENDER',flush=True)

if __name__=='__main__':main()
