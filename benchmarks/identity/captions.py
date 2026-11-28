"""The channel's caption look (identity, owner 2026-11-27, playbook section 11): heavy type, with the numbers in safety yellow so
the big plain numbers jump out. The font (Inter Display Black, SIL OFL 1.1) is bundled in assets/fonts, so CI renders the same
captions. Captions stay the only words on screen."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "assets/fonts"
FONT_FILE = FONT_DIR / "InterDisplay-Black.otf"
FONT_NAME = "Inter Display Black"
SIZE = 72
SPACING = 1.5                         # a little tracking: the heavy face's word spaces read tight at phone size
STYLE = (f"Style: Caption,{FONT_NAME},{SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,{SPACING},0,1,6,2,2,90,90,420,1")
YELLOW = r"{\c&H0000D6FF&}"          # safety yellow (255, 214, 0) in ASS order &HAABBGGRR
WHITE = r"{\c&H00FFFFFF&}"
MAX_LINE_PX = 900                     # 1080 minus the side margins
NUMBER_WORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
                "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million", "billion", "half", "double",
                "twice", "percent"}


def is_number(token: str) -> bool:
    """A number in words or digits, alone or hyphenated with others (fifty-thousand-pound, twenty-five)."""
    core = re.sub(r"^[^\w]+|[^\w]+$", "", token).lower()
    if not core:
        return False
    if re.search(r"\d", core):
        return True
    parts = core.split("-")
    return any(p in NUMBER_WORDS for p in parts)


def highlight(text: str) -> str:
    """Wrap every number token in safety yellow; line breaks (\\N) and spacing stay as they are."""
    out = []
    for line in text.split(r"\N"):
        out.append(" ".join(f"{YELLOW}{t}{WHITE}" if is_number(t) else t for t in line.split(" ")))
    return r"\N".join(out)


def line_px(text: str) -> float:
    """Width in pixels of one caption line (tags removed) in the caption font, with the tracking."""
    from PIL import ImageFont
    plain = re.sub(r"\{[^}]*\}", "", text)
    return ImageFont.truetype(str(FONT_FILE), SIZE).getlength(plain) + SPACING * max(0, len(plain) - 1)


def wrap(text: str) -> str:
    """Break any line wider than MAX_LINE_PX at the space that balances its two halves best (the heavy face runs wider than the
    narration build's own estimate; EP.36's "Afterwards, crews loosen" was 928 px)."""
    out = []
    for line in text.split(r"\N"):
        words = line.split(" ")
        if line_px(line) <= MAX_LINE_PX or len(words) < 2:
            out.append(line)
            continue
        best = min(range(1, len(words)), key=lambda k: max(line_px(" ".join(words[:k])), line_px(" ".join(words[k:]))))
        out += [" ".join(words[:best]), " ".join(words[best:])]
    return r"\N".join(out)


def restyle(ass_text: str) -> str:
    """The film.ass written by the narration build, in the channel's caption look: the style line replaced, over-wide lines broken
    in two, numbers highlighted."""
    lines = ass_text.splitlines()
    styles = [i for i, ln in enumerate(lines) if ln.startswith("Style: Caption,")]
    if len(styles) != 1:
        raise ValueError("expected exactly one Caption style line")
    lines[styles[0]] = STYLE
    out = []
    for ln in lines:
        if ln.startswith("Dialogue:"):
            head, text = ln.split(",,0,0,0,,", 1)
            ln = f"{head},,0,0,0,,{highlight(wrap(text))}"
        out.append(ln)
    return "\n".join(out) + "\n"


def ass_filter(path: Path) -> str:
    """The ffmpeg filter that burns the captions with the bundled font."""
    return f"ass={path}:fontsdir={FONT_DIR}"


def widest_line_px(ass_text: str) -> float:
    from PIL import ImageFont
    font = ImageFont.truetype(str(FONT_FILE), SIZE)
    widest = 0.0
    for ln in ass_text.splitlines():
        if ln.startswith("Dialogue:"):
            text = re.sub(r"\{[^}]*\}", "", ln.split(",,0,0,0,,", 1)[1])
            widest = max(widest, max(font.getlength(part) + SPACING * max(0, len(part) - 1) for part in text.split(r"\N")))
    return widest
