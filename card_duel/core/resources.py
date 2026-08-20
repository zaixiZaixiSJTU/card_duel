"""Card artwork loading and generated placeholder rendering."""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGE_SIZE = (160, 240)
BUTTON_PAD = (5, 8)


def resolve_resource_path(relative_path: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative_path
    return Path(__file__).resolve().parents[2] / relative_path


def encode_image(path: str | Path, size: tuple[int, int] = IMAGE_SIZE) -> bytes:
    with Image.open(path) as image:
        image.thumbnail(size, Image.Resampling.LANCZOS)
        return _encode_pil_image(image)


def load_character_images(character_id: int, registry) -> tuple[list[bytes], int]:
    """Load available artwork and generate every missing registered card."""
    image_dir = resolve_resource_path(f"assets/cards/{character_id}")
    definitions = {item.card_id: item for item in registry.get_catalog(character_id)}
    maximum = max(definitions, default=0)
    images = []
    for card_id in range(maximum + 1):
        image_path = image_dir / f"img-{card_id}.jpg"
        if image_path.exists():
            images.append(encode_image(image_path))
        else:
            images.append(_render_card_placeholder(definitions.get(card_id)))
    return images, maximum


def render_card(
    definition,
    *,
    effective_cost=None,
    creature_health=None,
    outline="#2E2A26",
) -> bytes:
    """Render one generated card with optional live cost, health, and border."""
    return _render_card_placeholder(
        definition,
        effective_cost=effective_cost,
        creature_health=creature_health,
        outline=outline,
    )


def _render_card_placeholder(
    definition,
    *,
    effective_cost=None,
    creature_health=None,
    outline="#2E2A26",
) -> bytes:
    image = Image.new("RGB", IMAGE_SIZE, "#FFFDF8")
    draw = ImageDraw.Draw(image)
    line_width = 4 if outline != "#2E2A26" else 2
    draw.rounded_rectangle(
        (1, 1, 158, 238), radius=10, outline=outline, width=line_width
    )
    if definition is None or definition.card_id == 0:
        return _encode_pil_image(image)

    accent = {
        "技能": "#6F89A8",
        "物品": "#C39A55",
        "生物": "#C86655",
        "见闻": "#719775",
        "形态": "#8B79A8",
    }.get(definition.card_type, "#837A70")
    draw.rounded_rectangle((8, 8, 152, 40), radius=6, fill=accent)
    draw.text((13, 13), definition.name, fill="#FFFDF8", font=_font(18, True))
    shown_cost = definition.cost if effective_cost is None else effective_cost
    cost_text = "X" if shown_cost is None else str(shown_cost)
    cost_color = "#2E7D32" if effective_cost != definition.cost else accent
    draw.ellipse((124, 48, 151, 75), outline=cost_color, width=3)
    draw.text((133, 52), cost_text, fill=cost_color, font=_font(12, True))
    draw.text((12, 52), definition.card_type, fill=accent, font=_font(12))
    for line_number, line in enumerate(_wrap_text(definition.description, 13)[:8]):
        draw.text((12, 84 + line_number * 18), line, fill="#2E2A26", font=_font(11))
    if creature_health is not None:
        draw.ellipse((122, 202, 153, 233), fill="#C86655")
        draw.text(
            (131, 207),
            str(max(0, creature_health)),
            fill="#FFFDF8",
            font=_font(14, True),
        )
    return _encode_pil_image(image)


def _font(size: int, bold: bool = False):
    names = ("msyhbd.ttc", "msyh.ttc") if bold else ("msyh.ttc",)
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wrap_text(text: str, width: int) -> list[str]:
    return [text[index : index + width] for index in range(0, len(text), width)]


def _encode_pil_image(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())
