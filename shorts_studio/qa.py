from __future__ import annotations
import json, subprocess
from pathlib import Path
from .subtitles import Caption, speech_gap_violations
from .timing import WordTiming

def subtitle_qa(captions:list[Caption], words:list[WordTiming], duration:float)->dict:
    bad=[c for c in captions if c.start<0 or c.end<c.start or c.end>duration+1e-3]
    gaps=speech_gap_violations(captions,words)
    return {"status":"PASS" if not bad and not gaps else "FAIL","invalid":len(bad),"speech_gaps":len(gaps)}

def probe_video(path:Path)->dict:
    p=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,r_frame_rate","-of","json",str(path)],capture_output=True,text=True,check=True)
    return json.loads(p.stdout)

def write_report(path:Path,data:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2),encoding="utf-8")
