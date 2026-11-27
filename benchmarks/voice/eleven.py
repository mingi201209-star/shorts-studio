"""The channel's own narration voice (ElevenLabs). Owner's choice 2026-11-27, for channel identity: a designed voice no other channel
uses, in place of the common edge-tts voice.

Talks to api.elevenlabs.io through the session's HTTPS proxy. The proxy adds the key, which is stored as a network secret on the
cloud environment (header xi-api-key); nothing here holds a key, and the header sent from here is a placeholder the proxy replaces.

Jobs:
- check: does the API answer with a key (plan tier only, nothing secret)?
- design: voice candidates from descriptions, each reading the same sample; writes the mp3 previews and their ids.
- create: save the chosen candidate as the channel's voice; writes examples/voice/channel-voice.json (the voice id is not secret).
- capture: narration lines in that voice with measured word timings. Written like the edge-tts capture (capture.json + beat_NN.mp3),
  so benchmarks/crumple_zone/level_beats.py and curious_mechanics_audio.build run unchanged.

usage:
  python3 -m benchmarks.voice.eleven check
  python3 -m benchmarks.voice.eleven design --out DIR --text "sample" --desc "voice one" --desc "voice two" ...
  python3 -m benchmarks.voice.eleven create --generated-id ID --name NAME --desc "description"
  python3 -m benchmarks.voice.eleven capture --plan PLAN.json --variant ID --out DIR"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

API = "https://api.elevenlabs.io"
ROOT = Path(__file__).resolve().parents[2]
VOICE_FILE = ROOT / "examples/voice/channel-voice.json"
DESIGN_MODEL = "eleven_multilingual_ttv_v2"
SPEECH_MODEL = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}


def _post(path: str, body: dict, timeout: float = 180.0) -> dict:
    import requests
    for attempt in range(4):
        r = requests.post(API + path, json=body, timeout=timeout, headers={"xi-api-key": "set-by-proxy", "Content-Type": "application/json"})
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(8 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise SystemExit(f"{path}: HTTP {r.status_code} {r.text[:300]}")
        return r.json()
    raise SystemExit(f"{path}: gave up")


def _get(path: str) -> tuple[int, dict | str]:
    import requests
    r = requests.get(API + path, timeout=60, headers={"xi-api-key": "set-by-proxy"})
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:300]


def words_from_alignment(text: str, alignment: dict) -> list[dict]:
    """One timing per whitespace-separated token of `text` (the capture format's rule: no invented timings). The alignment's
    characters spell the text; a token runs from its first letter or digit's start to its last one's end (punctuation does not
    stretch it)."""
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    if "".join(chars) != text:
        raise ValueError("the alignment does not spell the text (normalised?)")
    out = []
    for m in re.finditer(r"\S+", text):
        idx = [i for i in range(m.start(), m.end()) if chars[i].isalnum()] or list(range(m.start(), m.end()))
        out.append({"text": re.sub(r"^[^\w']+|[^\w']+$", "", m.group()), "start": round(starts[idx[0]], 6), "end": round(ends[idx[-1]], 6)})
    return out


def check() -> None:
    code, body = _get("/v1/user/subscription")
    tier = body.get("tier") if isinstance(body, dict) else None
    print(json.dumps({"http": code, "tier": tier, "character_limit": body.get("character_limit") if isinstance(body, dict) else None,
                      "character_count": body.get("character_count") if isinstance(body, dict) else None}))


def design(out: Path, text: str, descs: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for k, desc in enumerate(descs, 1):
        r = _post("/v1/text-to-voice/design", {"voice_description": desc, "model_id": DESIGN_MODEL, "text": text, "auto_generate_text": False})
        for j, pv in enumerate(r.get("previews", []), 1):
            mp3 = out / f"cand{k}_{j}.mp3"
            mp3.write_bytes(base64.b64decode(pv["audio_base_64"]))
            rows.append({"candidate": f"{k}.{j}", "description": desc, "generated_voice_id": pv["generated_voice_id"], "file": mp3.name})
        print(f"designed {k}: {len(r.get('previews', []))} previews", flush=True)
        time.sleep(2)
    (out / "candidates.json").write_text(json.dumps({"text": text, "model": DESIGN_MODEL, "candidates": rows}, indent=1))


def create(generated_id: str, name: str, desc: str) -> None:
    r = _post("/v1/text-to-voice", {"voice_name": name, "voice_description": desc, "generated_voice_id": generated_id})
    VOICE_FILE.parent.mkdir(parents=True, exist_ok=True)
    VOICE_FILE.write_text(json.dumps({"voice_id": r["voice_id"], "name": name, "description": desc, "generated_voice_id": generated_id,
                                      "speech_model": SPEECH_MODEL, "settings": SETTINGS}, indent=1) + "\n")
    print("voice_id", r["voice_id"])


def _duration(path: Path) -> float:
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], text=True))


def capture(plan: Path, variant: str, out: Path) -> None:
    voice = json.loads(VOICE_FILE.read_text())
    v = next(x for x in json.loads(plan.read_text())["variants"] if x["id"] == variant)
    out.mkdir(parents=True, exist_ok=True)
    beats = []
    for i, b in enumerate(v["beats"], 1):
        text = b["narration_en"]
        r = _post(f"/v1/text-to-speech/{voice['voice_id']}/with-timestamps",
                  {"text": text, "model_id": voice["speech_model"], "voice_settings": voice["settings"]})
        mp3 = out / f"beat_{i:02}.mp3"
        mp3.write_bytes(base64.b64decode(r["audio_base64"]))
        words = words_from_alignment(text, r["alignment"])
        dur = _duration(mp3)
        beats.append({"text": text, "voice": f"elevenlabs:{voice['name']}:{voice['voice_id']}", "rate": "model default", "words": words,
                      "duration": dur, "audio_sha256": hashlib.sha256(mp3.read_bytes()).hexdigest(),
                      "available_seconds": b["end"] - b["start"], "fits": dur <= b["end"] - b["start"] - 0.1})
        (out / f"beat_{i:02}.json").write_text(json.dumps(beats[-1], indent=1))
        print(f"line {i}: {dur:.2f}s, {len(words)} words", flush=True)
    (out / "capture.json").write_text(json.dumps({"variant": variant, "beats": beats}, indent=2) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    d = sub.add_parser("design")
    d.add_argument("--out", type=Path, required=True)
    d.add_argument("--text", required=True)
    d.add_argument("--desc", action="append", required=True)
    c = sub.add_parser("create")
    c.add_argument("--generated-id", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--desc", required=True)
    k = sub.add_parser("capture")
    k.add_argument("--plan", type=Path, required=True)
    k.add_argument("--variant", required=True)
    k.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.cmd == "check":
        check()
    elif a.cmd == "design":
        design(a.out, a.text, a.desc)
    elif a.cmd == "create":
        create(a.generated_id, a.name, a.desc)
    else:
        capture(a.plan, a.variant, a.out)


if __name__ == "__main__":
    main()
