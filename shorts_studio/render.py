from __future__ import annotations
import asyncio, json, os, shutil, subprocess, time, urllib.error, urllib.request
from pathlib import Path
from .project import load_project
from .tts import edge_tts_with_boundaries
from .subtitles import segment
from .qa import subtitle_qa, write_report
from .visual_qa import asset_visual_gate, default_vision_provider, evaluate_scene_semantics, production_semantic_ok

def _srt_time(x:float)->str:
    ms=round(x*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def write_srt(path:Path,caps):
    blocks=[f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}" for i,c in enumerate(caps,1)]
    path.write_text("\n\n".join(blocks)+"\n",encoding="utf-8")

_TRANSIENT_HTTP_CODES={429,500,502,503,504}

def _download(url:str,path:Path,max_attempts:int=4)->Path:
    """Download with bounded retry+backoff for transient server-side errors
    (rate limiting, brief outages). Permanent client errors (404, 403, ...)
    fail immediately -- retrying them would never succeed and would just
    delay the recovery loop's move to the next candidate."""
    req=urllib.request.Request(url,headers={"User-Agent":"shorts-studio/0.1"})
    last_error=None
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req,timeout=60) as src, path.open("wb") as dst:
                shutil.copyfileobj(src,dst)
            return path
        except urllib.error.HTTPError as e:
            last_error=e
            if e.code not in _TRANSIENT_HTTP_CODES or attempt==max_attempts-1:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_error=e
            if attempt==max_attempts-1:
                raise
        time.sleep(2**(attempt+1))
    raise last_error  # pragma: no cover - loop always returns or raises above

def _title_filter(title:str|None)->str:
    if not title:
        return ""
    safe=title.replace("\\","\\\\").replace("'","\\'").replace(":","\\:")
    return (
        f",drawtext=text='{safe}':"
        "fontcolor=white:fontsize=58:borderw=5:bordercolor=black:"
        "x=(w-text_w)/2:y=105"
    )

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
    style="Alignment=2,MarginV=48,FontSize=18,Outline=2,Shadow=0,Bold=1"
    # Preserve the complete source image.  The old fill+crop path could discard
    # most of a landscape archival photo/document when forcing it into 9:16.
    # Build a full-frame blurred backdrop, then place a sharp contain-fit copy
    # over it. This keeps every source pixel visible while avoiding empty bars.
    bg="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:8"
    fg="scale=1000:1720:force_original_aspect_ratio=decrease"
    return (
        f"split=2[bgsrc][fgsrc];"
        f"[bgsrc]{bg}[bg];"
        f"[fgsrc]{fg}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,{move}:s=1080x1920:fps={fps},"
        f"subtitles={srt.as_posix()}:force_style='{style}'"
        f"{_title_filter(scene.overlay_title)}"
    )

def _rasterize_svg(svg:Path, output:Path, width:int=1080, height:int=1920)->Path:
    # ffmpeg has no built-in SVG decoder (it only demuxes "svg_pipe", it cannot
    # decode the vector content), so SVG assets must be rasterized before
    # ffmpeg ever sees them.
    if not shutil.which("rsvg-convert"):
        raise RuntimeError("rsvg-convert (apt package librsvg2-bin) is required to rasterize SVG assets")
    subprocess.run(["rsvg-convert","-w",str(width),"-h",str(height),str(svg),"-o",str(output)],check=True,capture_output=True)
    return output

def _resolve_asset(candidate:dict, build:Path, scene_id:str, index:int)->Path|None:
    asset=candidate.get("asset"); asset_url=candidate.get("asset_url")
    path=None
    if asset and Path(asset).exists():
        path=Path(asset)
    elif asset_url:
        suffix=Path(asset_url.split('?')[0]).suffix or '.jpg'
        path=_download(asset_url, build/f"{scene_id}_asset_{index}{suffix}")
    if path and path.suffix.lower()==".svg":
        path=_rasterize_svg(path, build/f"{scene_id}_asset_{index}.png")
    return path

def _composite_scene_clip(scene, asset:Path|None, audio:Path, srt:Path, duration:float, fps:int, build:Path, index:int)->Path:
    clip=build/(f"{scene.id}.mp4" if index==0 else f"{scene.id}_r{index}.mp4")
    if asset:
        cmd=["ffmpeg","-y","-loop","1","-framerate",str(fps),"-i",str(asset),"-i",str(audio),"-t",str(duration),"-vf",_visual_filter(scene,srt,fps),"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(clip)]
    else:
        vf=f"subtitles={srt.as_posix()}:force_style='Alignment=2,MarginV=48,FontSize=18,Outline=2,Bold=1'{_title_filter(scene.overlay_title)}"
        cmd=["ffmpeg","-y","-f","lavfi","-i",f"color=c=0x20242b:s=1080x1920:r={fps}:d={duration}","-i",str(audio),"-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(clip)]
    try:
        subprocess.run(cmd,check=True,capture_output=True,text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed compositing {scene.id}: {e.stderr[-2000:] if e.stderr else e}") from e
    return clip

def _synthesize_scene_audio(scene, build:Path)->tuple[Path,float,Path,dict]:
    audio=build/f"{scene.id}.mp3"; timing=build/f"{scene.id}.timing.json"
    words=asyncio.run(edge_tts_with_boundaries(scene.narration,audio,timing))
    duration=max(w.end for w in words)+.25
    caps=segment(words,duration)
    q=subtitle_qa(caps,words,duration)
    srt=build/f"{scene.id}.srt"; write_srt(srt,caps)
    return audio,duration,srt,{"scene":scene.id,**q}

def _asset_candidates(scene)->list[dict]:
    primary={"asset":scene.asset,"asset_url":scene.asset_url,"attribution":scene.attribution}
    return [primary]+[c.model_dump() for c in scene.recovery_candidates]

def _render_scene_with_recovery(scene, audio:Path, duration:float, srt:Path, fps:int, build:Path, max_attempts:int, provider)->dict:
    """Render a scene's visual clip, running semantic visual QA and, on FAIL,
    swapping to the next declared fallback asset and re-rendering ONLY this
    scene's clip (never the whole production) until it passes or the bounded
    recovery budget is exhausted."""
    candidates=_asset_candidates(scene)
    last_index_tried=-1; last_error=None; result=None; clip=None; used=None
    for index in range(min(len(candidates), max_attempts+1)):
        last_index_tried=index
        try:
            asset=_resolve_asset(candidates[index],build,scene.id,index)
            clip=_composite_scene_clip(scene,asset,audio,srt,duration,fps,build,index)
        except Exception as e:
            last_error=f"candidate {index} failed to resolve/render: {e}"
            result={"scene":scene.id,"status":"FAIL","reason":last_error}
            continue
        used={"index":index,"asset":str(asset) if asset else None,"attribution":candidates[index].get("attribution")}
        if not scene.visual_qa_requirements:
            result={"scene":scene.id,"status":"NOT_EVALUATED","reason":"no visual_qa_requirements declared"}
            break
        frame=build/f"{scene.id}_qa.jpg"
        result=evaluate_scene_semantics(scene,clip,provider,frame,asset_path=asset)
        if result["status"]!="FAIL":
            break
        last_error=result.get("reason")
    recovery_attempts=last_index_tried  # index 0 is the primary asset, not a recovery
    more_candidates_available=(last_index_tried+1)<len(candidates)
    exhausted=result["status"]=="FAIL" and (not more_candidates_available or recovery_attempts>=max_attempts)
    result={**result,"recovery_attempts":recovery_attempts,"recovery_exhausted":bool(exhausted)}
    return {"clip":clip,"source":used,"semantic":result}

def render(manifest:str,dry_run:bool=False)->dict:
    p=load_project(manifest)
    if dry_run: return {"status":"PASS","scenes":len(p.scenes),"mode":"dry-run"}
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg/ffprobe required")
    build=Path("build"); dist=Path("dist"); build.mkdir(exist_ok=True); dist.mkdir(exist_ok=True)
    provider=default_vision_provider()
    concat=[]; subtitle_reports=[]; sources=[]; semantic_results=[]
    for scene in p.scenes:
        audio,duration,srt,q=_synthesize_scene_audio(scene,build)
        subtitle_reports.append(q)
        if q["status"]!="PASS": raise RuntimeError(f"subtitle QA failed: {scene.id}: {q}")
        outcome=_render_scene_with_recovery(scene,audio,duration,srt,p.fps,build,p.max_visual_recovery_attempts,provider)
        if outcome["clip"] is None:
            raise RuntimeError(f"scene {scene.id}: no asset candidate could be rendered: {outcome['semantic'].get('reason')}")
        concat.append(outcome["clip"])
        sources.append({"scene":scene.id,"asset":outcome["source"]["asset"] if outcome["source"] else None,"attribution":outcome["source"]["attribution"] if outcome["source"] else None,"candidate_index":outcome["source"]["index"] if outcome["source"] else None,"recovery_attempts":outcome["semantic"].get("recovery_attempts",0)})
        if scene.visual_qa_requirements:
            semantic_results.append(outcome["semantic"])
    lst=build/"concat.txt"; lst.write_text("\n".join(f"file '{x.resolve()}'" for x in concat),encoding="utf-8")
    final=dist/"final.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(final)],check=True,capture_output=True)
    probe=json.loads(subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,width,height,r_frame_rate","-show_entries","format=duration","-of","json",str(final)],capture_output=True,text=True,check=True).stdout)
    visual=asset_visual_gate(p,sources)
    if any(r["status"]=="FAIL" for r in semantic_results): semantic_status="FAIL"
    elif semantic_results and all(r["status"]=="PASS" for r in semantic_results): semantic_status="PASS"
    else: semantic_status="NOT_EVALUATED"
    semantic={"status":semantic_status,"results":semantic_results}
    require_semantic=bool(os.environ.get("SHORTS_REQUIRE_SEMANTIC_QA"))
    semantic_ok=production_semantic_ok(semantic["status"],require_semantic)
    overall="PASS" if visual["structural_status"]=="PASS" and semantic_ok and all(x["status"]=="PASS" for x in subtitle_reports) else "FAIL"
    report={"status":overall,"subtitle_reports":subtitle_reports,"visual_qa":visual,"semantic_visual_qa":semantic,"semantic_required":require_semantic,"sources":sources,"probe":probe,"output":str(final)}
    write_report(dist/"qa_report.json",report)
    if overall!="PASS":
        raise RuntimeError(f"QA failed: {report}")
    return report
