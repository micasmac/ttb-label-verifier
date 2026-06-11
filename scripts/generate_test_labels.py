"""Generate test label images for the TTB Label Verifier.

Each label targets a specific acceptance criterion from the spec. Rendering
labels programmatically (instead of with AI image generation) gives exact
control over the text, so every test case is deterministic.

Usage:
    python scripts/generate_test_labels.py [output_dir]
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
SERIF_BOLD = FONT_DIR / "DejaVuSerif-Bold.ttf"
SERIF = FONT_DIR / "DejaVuSerif.ttf"
SANS = FONT_DIR / "DejaVuSans.ttf"
SANS_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

CORRECT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should "
    "not drink alcoholic beverages during pregnancy because of the risk of "
    "birth defects. (2) Consumption of alcoholic beverages impairs your "
    "ability to drive a car or operate machinery, and may cause health "
    "problems."
)
TITLE_CASE_WARNING = CORRECT_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")

W, H = 900, 1300


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _center(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill="#1b1b1b") -> int:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((W - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)
    return y + (box[3] - box[1])


def make_label(
    *,
    brand: str,
    class_type: str,
    abv: str,
    net: str,
    warning: str,
    extra: str = "",
    bg: str = "#f5efdf",
) -> Image.Image:
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    # Double border, classic spirits-label style
    d.rectangle([24, 24, W - 24, H - 24], outline="#3a2c1a", width=5)
    d.rectangle([40, 40, W - 40, H - 40], outline="#3a2c1a", width=2)

    y = 120
    # Small drawn diamond ornament (avoids font glyph availability issues)
    d.polygon([(W // 2, y), (W // 2 + 16, y + 20), (W // 2, y + 40), (W // 2 - 16, y + 20)], fill="#7a5c2e")
    y += 76

    # Brand name — may wrap on long names
    for line in textwrap.wrap(brand, width=16) or [brand]:
        y = _center(d, line, y, _font(SERIF_BOLD, 72)) + 22

    y += 12
    d.line([(W // 2 - 180, y), (W // 2 + 180, y)], fill="#7a5c2e", width=3)
    y += 40

    for line in textwrap.wrap(class_type, width=26):
        y = _center(d, line, y, _font(SERIF, 42)) + 16

    y += 50
    y = _center(d, abv, y, _font(SANS_BOLD, 38)) + 26
    y = _center(d, net, y, _font(SANS_BOLD, 38)) + 26
    if extra:
        y = _center(d, extra, y, _font(SANS, 26), "#4a4a4a") + 20

    # Government warning block near the bottom
    wy = H - 330
    d.line([(70, wy - 24), (W - 70, wy - 24)], fill="#3a2c1a", width=2)
    warning_font = _font(SANS, 23)
    for line in textwrap.wrap(warning, width=58):
        d.text((70, wy), line, font=warning_font, fill="#1b1b1b")
        wy += 31

    return img


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("test_labels")
    out.mkdir(parents=True, exist_ok=True)

    # 1. Correct label for TTB-2026-0001 — expect all 5 fields to match.
    make_label(
        brand="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        abv="45% Alc./Vol. (90 Proof)",
        net="750 mL",
        warning=CORRECT_WARNING,
        extra="Distilled and bottled in Bardstown, Kentucky",
    ).save(out / "label_01_correct_all_match.png")

    # 2. Title-case warning for TTB-2026-0001 — expect Government warning MISMATCH
    #    (Jenny's real-world rejection example).
    make_label(
        brand="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        abv="45% Alc./Vol. (90 Proof)",
        net="750 mL",
        warning=TITLE_CASE_WARNING,
        extra="Distilled and bottled in Bardstown, Kentucky",
    ).save(out / "label_02_title_case_warning_mismatch.png")

    # 3. All-caps brand for TTB-2026-0002 (application says "Stone's Throw") —
    #    expect brand MATCH with a formatting note (Dave's example).
    make_label(
        brand="STONE'S THROW",
        class_type="India Pale Ale",
        abv="6.8% Alc./Vol.",
        net="355 mL",
        warning=CORRECT_WARNING,
        extra="Stone's Throw Brewing Co., Portland, Oregon",
        bg="#e8eedf",
    ).save(out / "label_03_caps_brand_still_matches.png")

    # 4. Wrong ABV and inconsistent proof for TTB-2026-0001 —
    #    expect Alcohol content MISMATCH (40% stated, app says 45%).
    make_label(
        brand="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        abv="40% Alc./Vol. (80 Proof)",
        net="750 mL",
        warning=CORRECT_WARNING,
        extra="Distilled and bottled in Bardstown, Kentucky",
    ).save(out / "label_04_wrong_abv_mismatch.png")

    # 5. Missing warning + wrong volume for TTB-2026-0004 —
    #    expect Net contents MISMATCH and Government warning MISMATCH (not found).
    make_label(
        brand="HARBOR LIGHTS",
        class_type="London Dry Gin",
        abv="47% Alc./Vol. (94 Proof)",
        net="750 mL",  # application says 1 L
        warning="",  # no warning printed at all
        extra="Harbor Lights Spirits, Seattle, Washington",
        bg="#e3e9ef",
    ).save(out / "label_05_missing_warning_wrong_volume.png")

    # 6. Heavily blurred label — expect the "unreadable image" error path.
    blurred = make_label(
        brand="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        abv="45% Alc./Vol. (90 Proof)",
        net="750 mL",
        warning=CORRECT_WARNING,
    ).filter(ImageFilter.GaussianBlur(radius=14))
    blurred.save(out / "label_06_blurry_unreadable.png")

    print(f"Wrote 6 test labels to {out.resolve()}")


if __name__ == "__main__":
    main()
