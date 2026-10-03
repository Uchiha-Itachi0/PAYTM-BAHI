"""
Render every phone in docs/screens.html to its own PNG in docs/screens/.

The deck places these images, so they must come from the same HTML the team
reviews. Each phone is cut out with the page's own stylesheet, drawn by
headless Chrome at 2x, and trimmed to its edge. Run from the repo root:

    python3 docs/render_screens.py
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SRC = Path("docs/screens.html")
OUT = Path("docs/screens")

NAMES = {
    "A1": "book", "A2": "speak", "A3": "tonight", "A4": "add",
    "B0": "scan", "B1": "confirm", "B2": "mybook", "B3": "cleared",
    "C1": "inbox", "C2": "dispute", "C3": "unpaid",
}

# Fixed phone height so every render is the same size in the deck.
FRAME = """
<style>
  html,body{margin:0;padding:0;background:#ffffff}
  body{zoom:2}
  .unit{width:330px;margin:0}
  .phone{box-shadow:none;border:1px solid #d7dde5;height:648px;min-height:648px}
</style>
"""


def phone_after(html: str, start: int) -> str:
    """The first <div class="phone…"> after `start`, with its nested divs."""
    open_at = html.index('<div class="phone', start)
    depth, i = 0, open_at
    for m in re.finditer(r"<div\b|</div>", html[open_at:]):
        depth += 1 if m.group() == "<div" else -1
        if depth == 0:
            i = open_at + m.end()
            break
    return html[open_at:i]


def main() -> None:
    html = SRC.read_text(encoding="utf-8")
    head = html[: html.index("</style>") + len("</style>")]
    head = head.replace("<title>BAHI Screens</title>", '<meta charset="utf-8">')

    with tempfile.TemporaryDirectory() as tmp:
        for m in re.finditer(r"<!-- ([ABC]\d)\b", html):
            key = m.group(1)
            page = Path(tmp) / f"{key}.html"
            page.write_text(
                head + FRAME + '<div class="unit">' + phone_after(html, m.end())
                + "</div>",
                encoding="utf-8",
            )
            shot = Path(tmp) / f"{key}.png"
            subprocess.run(
                [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                 "--force-device-scale-factor=2", "--window-size=700,1400",
                 "--virtual-time-budget=4000", f"--screenshot={shot}",
                 page.as_uri()],
                check=True, capture_output=True,
            )
            im = Image.open(shot).convert("RGB")
            box = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
            out = OUT / f"{key}-{NAMES[key]}.png"
            im.crop(box).save(out)
            print(f"{out}  {im.crop(box).size}")


if __name__ == "__main__":
    main()
