"""Card artwork loading and generated placeholder rendering."""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGE_SIZE = (120, 180)
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
    """Load a consecutive image pack or generate cards from the registry."""
    image_dir = resolve_resource_path(f"assets/cards/{character_id}")
    images: list[bytes] = []
    card_id = 0
    while image_dir.exists():
        image_path = image_dir / f"img-{card_id}.jpg"
        if not image_path.exists():
            break
        images.append(encode_image(image_path))
        card_id += 1
    if images:
        return images, card_id - 1
    return _generate_registered_card_images(character_id, registry)


def _generate_registered_card_images(
    character_id: int, registry
) -> tuple[list[bytes], int]:
    definitions = {item.card_id: item for item in registry.get_catalog(character_id)}
    playable_ids = [card_id for card_id in definitions if card_id]
    if not playable_ids:
        return [], 0
    maximum = max(definitions)
    return [
        _render_card_placeholder(definitions.get(card_id))
        for card_id in range(maximum + 1)
    ], maximum


def _render_card_placeholder(definition) -> bytes:
    image = Image.new("RGB", IMAGE_SIZE, "#FFFDF8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 118, 178), radius=8, outline="#2E2A26", width=2)
    if definition is None or definition.card_id == 0:
        return _encode_pil_image(image)

    accent = {
        "技能": "#6F89A8",
        "物品": "#C39A55",
        "生物": "#C86655",
        "见闻": "#719775",
        "形态": "#8B79A8",
    }.get(definition.card_type, "#837A70")
    draw.rounded_rectangle((7, 7, 113, 31), radius=5, fill=accent)
    draw.text((11, 10), definition.name, fill="#FFFDF8", font=_font(14, True))
    cost_text = "X" if definition.cost is None else str(definition.cost)
    draw.ellipse((92, 36, 112, 56), outline=accent, width=2)
    draw.text((99, 39), cost_text, fill=accent, font=_font(9))
    draw.text((10, 40), definition.card_type, fill=accent, font=_font(9))
    for line_number, line in enumerate(_wrap_text(definition.description, 11)[:7]):
        draw.text((10, 66 + line_number * 14), line, fill="#2E2A26", font=_font(8))
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
