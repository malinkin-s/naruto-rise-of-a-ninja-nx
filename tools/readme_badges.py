#!/usr/bin/env python3
"""The README badges (docs/media/badges.svg, badges_ru.svg) in the portfolio's dark palette ("Ночной лист").

One image per language, two rows of the same width: the port's current state on top, platform / renderer / license
below, so the block stays aligned instead of wrapping like separate badges. Larger than shields.io's (32 px rows,
16 px text). Text widths are measured with ImageMagick (Noto Sans; values in bold) and pinned with textLength, so the
block looks the same whatever font the viewer has.
  python3 tools/readme_badges.py      (edit ROWS when the port's state changes)
"""
import pathlib
import subprocess
from xml.sax.saxutils import escape

PANEL, TEXT = "#1C2024", "#E6E1D3"
SIGNAL, SLATE, OCHRE = "#5CA382", "#7FA0B4", "#C2AC63"
DARK = "#14171A"  # value text on a coloured field

# language suffix: rows of (label, value, colour)
ROWS = {
    "": [
        [("status", "0.1.2 · test build · story 20-30 FPS, fights 32-47 FPS", SIGNAL)],
        [("platform", "Nintendo Switch (homebrew)", SLATE), ("renderer", "Renut · deko3d", SLATE),
         ("license", "GPL-3.0", OCHRE)],
    ],
    "_ru": [
        [("состояние", "0.1.2 · тестовая сборка · сюжет 20–30 FPS, бои 32–47 FPS", SIGNAL)],
        [("платформа", "Nintendo Switch (homebrew)", SLATE), ("рендерер", "Renut · deko3d", SLATE),
         ("лицензия", "GPL-3.0", OCHRE)],
    ],
}

HEIGHT, SIZE, PAD, GAP = 32, 16, 14, 10
FONT = "'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif"


def width(text: str, bold: bool = False) -> int:
    font = "Noto-Sans-Bold" if bold else "Noto-Sans-Regular"
    out = subprocess.run(["magick", "-font", font, "-pointsize", str(SIZE), f"label:{text}", "-format", "%w",
                          "info:"], capture_output=True, text=True, check=True).stdout
    return int(out)


def natural(row):
    return sum(width(l) + width(v, True) + 4 * PAD for l, v, _ in row) + GAP * (len(row) - 1)


def badges(rows) -> str:
    total = max(natural(r) for r in rows)
    parts, y = [], 0
    for row in rows:
        # The spare width of a shorter row goes evenly into its value fields, so every row ends at the same edge.
        spare = (total - natural(row)) / len(row)
        x = 0.0
        for label, value, colour in row:
            lw, vw = width(label), width(value, True)
            left, right = lw + 2 * PAD, vw + 2 * PAD + spare
            base = y + HEIGHT / 2 + SIZE * 0.35
            parts.append(f'  <rect x="{x:.1f}" y="{y}" width="{left}" height="{HEIGHT}" fill="{PANEL}"/>')
            parts.append(f'  <rect x="{x + left:.1f}" y="{y}" width="{right:.1f}" height="{HEIGHT}" fill="{colour}"/>')
            parts.append(f'  <text x="{x + PAD:.1f}" y="{base:.1f}" fill="{TEXT}" textLength="{lw}" '
                         f'lengthAdjust="spacingAndGlyphs">{escape(label)}</text>')
            parts.append(f'  <text x="{x + left + right / 2:.1f}" y="{base:.1f}" fill="{DARK}" font-weight="700" '
                         f'text-anchor="middle" textLength="{vw}" lengthAdjust="spacingAndGlyphs">{escape(value)}</text>')
            x += left + right + GAP
        y += HEIGHT + GAP
    height = y - GAP
    title = " · ".join(f"{l}: {v}" for row in rows for l, v, _ in row)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{height}" viewBox="0 0 {total} {height}" '
            f'role="img" aria-label="{escape(title)}">\n  <title>{escape(title)}</title>\n'
            f'  <g font-family="{FONT}" font-size="{SIZE}">\n' + "\n".join(parts) + "\n  </g>\n</svg>\n")


def main() -> None:
    out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "media"
    for suffix, rows in ROWS.items():
        (out / f"badges{suffix}.svg").write_text(badges(rows), encoding="utf-8")
        print(f"docs/media/badges{suffix}.svg")


if __name__ == "__main__":
    main()
