from __future__ import annotations
import asyncio, json, shutil, subprocess
from pathlib import Path
from .project import load_project
from .tts import edge_tts_with_boundaries
from .subtitles import segment
from .qa import subtitle_qa, write_report

def _srt_time(x:float)->str:
    ms=round(x*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def write_srt(path:Path,caps):
    blocks=[f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}" for i,c in enumerate(caps,1)]
    path.write_text("\n\n".join(blocks)+"\n",encoding="utf-8")

def render(manifest:str,dry_run:bool=False)->dict:
    p=load_project(manifest)
    if dry_run: return {"status":"PASS","scenes":len(p.scenes),"mode":"dry-run"}
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"): raise RuntimeError("FFmpeg/ffprobe required")
    build=Path("build"); dist=Path("dist"); build.mkdir(exist_ok=True); dist.mkdir(exist_ok=True)
    concat=[]; reports=[]
    for n,scene in enumerate(p.scenes):
        audio=build/f"{scene.id}.mp3"; timing=build/f"{scene.id}.timing.json"
        words=asyncio.run(edge_tts_with_boundaries(scene.narration,audio,timing))
        duration=max(w.end for w in words)+.25
        caps=segment(words,duration); q=subtitle_qa(caps,words,duration); reports.append(q)
        if q["status"]!="PASS": raise RuntimeError(f"subtitle QA failed: {scene.id}: {q}")
        srt=build/f"{scene.id}.srt"; write_srt(srt,caps)
        clip=build/f"{scene.id}.mp4"
        # V1 deterministic motion background when no licensed asset is supplied.
        vf=f"scale=1200:2134,zoompan=z='min(zoom+0.0008,1.08)':d=1:s=1080x1920:fps={p.fps},subtitles={srt.as_posix()}:force_style='Alignment=2,MarginV=260,FontSize=18,Outline=2'"
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c=0x20242b:s=1200x2134:r={p.fps}:d={duration}","-i",str(audio),"-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(clip)],check=True)
        concat.append(clip)
    lst=build/"concat.txt"; lst.write_text("\n".join(f"file '{x.resolve()}'" for x in concat),encoding="utf-8")
    final=dist/"final.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(final)],check=True)
    report={"status":"PASS","subtitle_reports":reports,"semantic_visual_qa":"NOT_EVALUATED","output":str(final)}
    write_report(dist/"qa_report.json",report); return report
