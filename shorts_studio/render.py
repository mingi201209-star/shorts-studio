from __future__ import annotations
import asyncio, json, shutil, subprocess, urllib.request
from pathlib import Path
from .project import load_project
from .tts import edge_tts_with_boundaries
from .subtitles import segment
from .qa import subtitle_qa, write_report
from .visual_qa import asset_visual_gate

def _srt_time(x:float)->str:
    ms=round(x*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def write_srt(path:Path,caps):
    blocks=[f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}" for i,c in enumerate(caps,1)]
    path.write_text("\n\n".join(blocks)+"\n",encoding="utf-8")

def _download(url:str,path:Path)->Path:
    req=urllib.request.Request(url,headers={"User-Agent":"shorts-studio/0.1"})
    with urllib.request.urlopen(req,timeout=60) as src, path.open("wb") as dst:
        shutil.copyfileobj(src,dst)
    return path

def _visual_filter(scene, srt:Path, fps:int)->str:
    motion=scene.motion.type
    if motion=="pan_right":
        move="zoompan=z='1.10':x='(iw-iw/zoom)*on/180':y='(ih-ih/zoom)/2':d=1"
    elif motion=="pan_left":
        move="zoompan=z='1.10':x='(iw-iw/zoom)*(1-on/180)':y='(ih-ih/zoom)/2':d=1"
    elif motion=="pull_out":
        move="zoompan=z='max(1.0,1.12-on*0.0007)':d=1"
    else:
        move="zoompan=z='min(zoom+0.0007,1.12)':d=1"
    style="Alignment=2,MarginV=260,FontSize=18,Outline=2,Shadow=0,Bold=1"
    return f"scale=1400:2489:force_original_aspect_ratio=increase,crop=1400:2489,{move}:s=1080x1920:fps={fps},subtitles={srt.as_posix()}:force_style='{style}'"

def render(manifest:str,dry_run:bool=False)->dict:
    p=load_project(manifest)
    if dry_run: return {"status":"PASS","scenes":len(p.scenes),"mode":"dry-run"}
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg/ffprobe required")
    build=Path("build"); dist=Path("dist"); build.mkdir(exist_ok=True); dist.mkdir(exist_ok=True)
    concat=[]; reports=[]; sources=[]
    for scene in p.scenes:
        audio=build/f"{scene.id}.mp3"; timing=build/f"{scene.id}.timing.json"
        words=asyncio.run(edge_tts_with_boundaries(scene.narration,audio,timing))
        duration=max(w.end for w in words)+.25
        caps=segment(words,duration); q=subtitle_qa(caps,words,duration); reports.append({"scene":scene.id,**q})
        if q["status"]!="PASS": raise RuntimeError(f"subtitle QA failed: {scene.id}: {q}")
        srt=build/f"{scene.id}.srt"; write_srt(srt,caps)
        asset=None
        if scene.asset and Path(scene.asset).exists(): asset=Path(scene.asset)
        elif scene.asset_url: asset=_download(scene.asset_url,build/f"{scene.id}_asset{Path(scene.asset_url.split('?')[0]).suffix or '.jpg'}")
        clip=build/f"{scene.id}.mp4"
        if asset:
            cmd=["ffmpeg","-y","-loop","1","-framerate",str(p.fps),"-i",str(asset),"-i",str(audio),"-t",str(duration),"-vf",_visual_filter(scene,srt,p.fps),"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(clip)]
            sources.append({"scene":scene.id,"asset":str(asset),"attribution":scene.attribution})
        else:
            vf=f"subtitles={srt.as_posix()}:force_style='Alignment=2,MarginV=260,FontSize=18,Outline=2,Bold=1'"
            cmd=["ffmpeg","-y","-f","lavfi","-i",f"color=c=0x20242b:s=1080x1920:r={p.fps}:d={duration}","-i",str(audio),"-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(clip)]
        subprocess.run(cmd,check=True); concat.append(clip)
    lst=build/"concat.txt"; lst.write_text("\n".join(f"file '{x.resolve()}'" for x in concat),encoding="utf-8")
    final=dist/"final.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(final)],check=True)
    probe=json.loads(subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,width,height,r_frame_rate","-show_entries","format=duration","-of","json",str(final)],capture_output=True,text=True,check=True).stdout)
    visual=asset_visual_gate(p,sources)
    overall="PASS" if visual["structural_status"]=="PASS" and all(x["status"]=="PASS" for x in reports) else "FAIL"
    report={"status":overall,"subtitle_reports":reports,"visual_qa":visual,"sources":sources,"probe":probe,"output":str(final)}
    if overall!="PASS":
        write_report(dist/"qa_report.json",report)
        raise RuntimeError(f"QA failed: {report}")
    write_report(dist/"qa_report.json",report)
    return report
