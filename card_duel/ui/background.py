"""Generate a light paper background with restrained line doodles."""

from PIL import Image, ImageDraw

from card_duel.ui.theme import Theme


def _hex_to_rgb(hex_color):
    value = hex_color.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def make_paper_background(width, height):
    """Create a notebook-like background without external image assets."""
    image = Image.new("RGB", (width, height), _hex_to_rgb(Theme.BACKGROUND))
    drawing = ImageDraw.Draw(image)

    # Faint horizontal pencil rules establish the paper texture.
    rule_color = _hex_to_rgb("#E6DED1")
    for y_position in range(28, height, 32):
        drawing.line((0, y_position, width, y_position), fill=rule_color)

    ink = _hex_to_rgb("#B9AEA0")
    accent = _hex_to_rgb("#D7C5A8")

    # Small corner doodles keep the style playful without adding noise.
    drawing.arc((width - 150, 28, width - 48, 130), 195, 520, fill=ink, width=2)
    drawing.line(
        (width - 96, 58, width - 78, 84, width - 108, 78),
        fill=accent,
        width=3,
    )
    drawing.ellipse((34, height - 92, 54, height - 72), outline=ink, width=2)
    drawing.line((54, height - 82, 104, height - 82), fill=ink, width=2)
    drawing.line((80, height - 96, 80, height - 68), fill=accent, width=2)
    return image
