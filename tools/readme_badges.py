#!/usr/bin/env python3
"""The README badges (docs/media/badge_*.svg) in the portfolio's dark palette ("Ночной лист").

Larger than shields.io's (32 px high, 16 px text). Text widths are measured with ImageMagick (Noto Sans; values in
bold) and pinned with textLength, so the badge looks the same whatever font the viewer has.
  python3 tools/readme_badges.py      (edit BADGES when the port's state changes)
"""
import pathlib
import subprocess
from xml.sax.saxutils import escape

PANEL, TEXT = "#1C2024", "#E6E1D3"
SIGNAL, SLATE, OCHRE = "#5CA382", "#7FA0B4", "#C2AC63"
DARK = "#14171A"  # value text on a coloured field

# file stem: (label, value, colour)
BADGES = {
    "status": ("status", "runs on Switch · menus and fights · slow", SIGNAL),
    "status_ru": ("состояние", "работает на Switch · меню и бои · медленно", SIGNAL),
    "platform": ("platform", "Nintendo Switch (homebrew)", SLATE),
    "platform_ru": ("платформа", "Nintendo Switch (homebrew)", SLATE),
    "renderer": ("renderer", "Renut · deko3d", SLATE),
    "renderer_ru": ("рендерер", "Renut · deko3d", SLATE),
    "licence": ("licence", "GPL-3.0", OCHRE),
    "licence_ru": ("лицензия", "GPL-3.0", OCHRE),
}

HEIGHT, SIZE, PAD = 32, 16, 12


def width(text: str, bold: bool = False) -> int:
    font = "Noto-Sans-Bold" if bold else "Noto-Sans-Regular"
    out = subprocess.run(["magick", "-font", font, "-pointsize", str(SIZE), f"label:{text}", "-format", "%w",
                          "info:"], capture_output=True, text=True, check=True).stdout
    return int(out)


def badge(label: str, value: str, colour: str) -> str:
    lw, vw = width(label), width(value, bold=True)
    left, right = lw + 2 * PAD, vw + 2 * PAD
    total, base = left + right, HEIGHT / 2 + SIZE * 0.35
    font = "'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{HEIGHT}" role="img" aria-label="{escape(label)}: {escape(value)}">
  <title>{escape(label)}: {escape(value)}</title>
  <rect width="{left}" height="{HEIGHT}" fill="{PANEL}"/>
  <rect x="{left}" width="{right}" height="{HEIGHT}" fill="{colour}"/>
  <g font-family="{font}" font-size="{SIZE}">
    <text x="{PAD}" y="{base:.1f}" fill="{TEXT}" textLength="{lw}" lengthAdjust="spacingAndGlyphs">{escape(label)}</text>
    <text x="{left + PAD}" y="{base:.1f}" fill="{DARK}" font-weight="700" textLength="{vw}" lengthAdjust="spacingAndGlyphs">{escape(value)}</text>
  </g>
</svg>
'''


def main() -> None:
    out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "media"
    for stem, (label, value, colour) in BADGES.items():
        (out / f"badge_{stem}.svg").write_text(badge(label, value, colour), encoding="utf-8")
        print(f"docs/media/badge_{stem}.svg")


if __name__ == "__main__":
    main()
