"""Contact sheets for the visual review (see docs/episode-playbook.md).
  storyboard frames:  python3 scripts/episode/contact_sheet.py frames DIR 0,40,95,140 OUT.png [columns]
                      (DIR holds the renderer's --list output: frame_00000.png, frame_00040.png, ...)
  finished film:      python3 scripts/episode/contact_sheet.py video FILM.mp4 OUT.jpg [frames_per_second]
                      (one frame per second by default, two rows)"""
import subprocess
import sys
from pathlib import Path

from PIL import Image


def frames(directory: str, frame_list: str, out: str, columns: int = 8) -> None:
    fs = [int(x) for x in frame_list.split(",")]
    w, h = 216, 384
    rows = (len(fs) + columns - 1) // columns
    sheet = Image.new("RGB", (w * min(columns, len(fs)), h * rows))
    for i, f in enumerate(fs):
        p = Path(directory) / f"frame_{f:05d}.png"
        if p.exists():
            sheet.paste(Image.open(p).convert("RGB").resize((w, h)), ((i % columns) * w, (i // columns) * h))
    sheet.save(out)


def video(film: str, out: str, fps: float = 1.0) -> None:
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", film], text=True))
    n = int(dur * fps) + 1
    cols = (n + 1) // 2
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", film, "-vf", f"fps={fps},scale=180:320,tile={cols}x2", "-frames:v", "1", out], check=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "frames":
        frames(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 8)
    elif mode == "video":
        video(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 1.0)
    else:
        raise SystemExit(__doc__)
