"""Genera programmaticamente l'icona dell'app (lettera Q stilizzata).

Richiede pycairo: uv add --dev pycairo
Uso: uv run python scripts/generate_icon.py [size] [output_path]
"""

import sys
from pathlib import Path

import cairo


def generate_icon(path: Path, size: int = 32) -> None:
    """Genera icona PNG con lettera Q stilizzata.

    Tutte le coordinate sono proporzionali a `size` per supportare
    risoluzioni multiple (32, 48, 64, 128).
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    s = size / 32.0
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)

    # Sfondo arrotondato scuro
    radius = 6 * s
    ctx.new_sub_path()
    ctx.arc(size - radius, radius, radius, -0.5 * 3.14159, 0)
    ctx.arc(size - radius, size - radius, radius, 0, 0.5 * 3.14159)
    ctx.arc(radius, size - radius, radius, 0.5 * 3.14159, 3.14159)
    ctx.arc(radius, radius, radius, 3.14159, 1.5 * 3.14159)
    ctx.close_path()
    ctx.set_source_rgb(0.18, 0.20, 0.25)
    ctx.fill()

    # Lettera "Q" stilizzata in bianco
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(20 * s)
    ctx.set_source_rgb(0.95, 0.95, 0.95)
    extents = ctx.text_extents("Q")
    x = (size - extents.width) / 2 - extents.x_bearing
    y = (size - extents.height) / 2 - extents.y_bearing
    ctx.move_to(x, y)
    ctx.show_text("Q")

    # Freccia piccola (quiver = faretra) in colore accento
    ctx.set_source_rgb(0.35, 0.65, 0.95)
    ctx.set_line_width(1.5 * s)
    ctx.move_to(20 * s, 22 * s)
    ctx.line_to(27 * s, 22 * s)
    ctx.stroke()
    ctx.move_to(24 * s, 19 * s)
    ctx.line_to(27 * s, 22 * s)
    ctx.line_to(24 * s, 25 * s)
    ctx.stroke()

    surface.write_to_png(str(path))
    print(f"Icona generata: {path} ({size}x{size})")


if __name__ == "__main__":
    icon_size = int(sys.argv[1]) if len(sys.argv) > 1 else 32
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("command_quiver/assets/icon.png")
    generate_icon(path=output, size=icon_size)
