"""Label text extraction.

V1 DEMO MODE — no AI API key is used or required.
==================================================
To avoid exposing an API key behind a publicly deployed demo, this version
runs entirely on the DemoExtractor: any uploaded image returns the Old Tom
Distillery sample fields, which exercises the full workflow and all of the
deterministic comparison logic.

Live AI extraction is planned for a future version. The complete, working
integration is included below as commented-out boilerplate. To enable it:

  1. Uncomment the AnthropicExtractor class and its imports.
  2. Uncomment the `anthropic` line in requirements.txt and reinstall.
  3. Set ANTHROPIC_API_KEY in your environment (see .env.example).
  4. Uncomment the key check in get_extractor() at the bottom of this file.

The extractor sits behind a small interface (`LabelExtractor`) so the AI
provider can also be swapped entirely — important because TTB's network
blocks many outbound domains, and a production deployment may need a
self-hosted model instead of a cloud API.
"""

from __future__ import annotations

from typing import Protocol

from ..models import ExtractedLabel
from .comparison import GOVERNMENT_WARNING_TEXT

# --- Future version: uncomment for live AI extraction ----------------------
# import base64
# import json
# import os
# ----------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are reading a photo of an alcohol beverage label for a TTB compliance check.

Extract these fields exactly as they appear on the label (verbatim, preserving capitalization and punctuation):
- brand_name
- class_type (e.g. "Kentucky Straight Bourbon Whiskey", "India Pale Ale")
- alcohol_content (e.g. "45% Alc./Vol. (90 Proof)")
- net_contents (e.g. "750 mL")
- government_warning (the full warning statement, verbatim, including its heading exactly as capitalized on the label)

Rules:
- If a field is not visible or not legible, set it to null. Never guess.
- If the image is not an alcohol label or is too blurry/angled/glared to read, set "readable" to false and explain briefly in "notes".

Respond with ONLY a JSON object, no markdown fences, with keys:
brand_name, class_type, alcohol_content, net_contents, government_warning, readable, notes"""


class LabelExtractor(Protocol):
    def extract(self, image_bytes: bytes, media_type: str, filename: str | None = None) -> ExtractedLabel: ...


# --- Future version: live AI extraction (boilerplate, currently disabled) ---
#
# class AnthropicExtractor:
#     """Extracts label fields with a single Claude vision call.
#
#     One multimodal call returning structured JSON keeps latency near the
#     5-second target from the discovery interviews.
#     """
#
#     def __init__(self, model: str | None = None) -> None:
#         import anthropic
#
#         self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
#         self._model = model or os.getenv("EXTRACTION_MODEL", "claude-sonnet-4-20250514")
#
#     def extract(self, image_bytes: bytes, media_type: str, filename: str | None = None) -> ExtractedLabel:
#         response = self._client.messages.create(
#             model=self._model,
#             max_tokens=1024,
#             messages=[
#                 {
#                     "role": "user",
#                     "content": [
#                         {
#                             "type": "image",
#                             "source": {
#                                 "type": "base64",
#                                 "media_type": media_type,
#                                 "data": base64.standard_b64encode(image_bytes).decode(),
#                             },
#                         },
#                         {"type": "text", "text": EXTRACTION_PROMPT},
#                     ],
#                 }
#             ],
#         )
#         raw = "".join(block.text for block in response.content if block.type == "text")
#         raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
#         try:
#             data = json.loads(raw)
#         except json.JSONDecodeError:
#             return ExtractedLabel(readable=False, notes="The AI response could not be parsed.")
#         return ExtractedLabel(**{k: data.get(k) for k in ExtractedLabel.model_fields})
#
# ----------------------------------------------------------------------------


class DemoExtractor:
    """V1 extractor: simulates AI extraction without an API key.

    The bundled test labels are recognized by filename, and the extractor
    returns exactly the fields printed on each one — so every test case
    (wrong ABV, title-case warning, missing warning, blurry image, etc.)
    demonstrates its intended verification outcome offline. Other images
    fall back to the Old Tom sample data with an explanatory note.
    """

    _TITLE_CASE_WARNING = GOVERNMENT_WARNING_TEXT.replace(
        "GOVERNMENT WARNING:", "Government Warning:"
    )

    _OLD_TOM = dict(
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content="45% Alc./Vol. (90 Proof)",
        net_contents="750 mL",
        government_warning=GOVERNMENT_WARNING_TEXT,
    )

    _FIXTURES: dict[str, ExtractedLabel] = {
        "label_01_correct_all_match.png": ExtractedLabel(**_OLD_TOM),
        "label_02_title_case_warning_mismatch.png": ExtractedLabel(
            **{**_OLD_TOM, "government_warning": _TITLE_CASE_WARNING}
        ),
        "label_03_caps_brand_still_matches.png": ExtractedLabel(
            brand_name="STONE'S THROW",
            class_type="India Pale Ale",
            alcohol_content="6.8% Alc./Vol.",
            net_contents="355 mL",
            government_warning=GOVERNMENT_WARNING_TEXT,
        ),
        "label_04_wrong_abv_mismatch.png": ExtractedLabel(
            **{**_OLD_TOM, "alcohol_content": "40% Alc./Vol. (80 Proof)"}
        ),
        "label_05_missing_warning_wrong_volume.png": ExtractedLabel(
            brand_name="HARBOR LIGHTS",
            class_type="London Dry Gin",
            alcohol_content="47% Alc./Vol. (94 Proof)",
            net_contents="750 mL",
            government_warning=None,
        ),
        "label_06_blurry_unreadable.png": ExtractedLabel(
            readable=False,
            notes="Demo mode: this sample simulates an image too blurry to read.",
        ),
    }

    def extract(self, image_bytes: bytes, media_type: str, filename: str | None = None) -> ExtractedLabel:  # noqa: ARG002
        fixture = self._FIXTURES.get((filename or "").strip())
        if fixture is not None:
            return fixture.model_copy(
                update={"notes": fixture.notes or "Demo mode: scripted extraction for this sample label."}
            )
        return ExtractedLabel(
            **self._OLD_TOM,
            readable=True,
            notes=(
                "Demo mode: AI extraction is disabled in this version, so this "
                "image was not actually read — sample data returned. Use the "
                "sample labels in the gallery to see each verification outcome."
            ),
        )


def get_extractor() -> LabelExtractor:
    # Future version: enable live AI extraction by uncommenting:
    # if os.getenv("ANTHROPIC_API_KEY"):
    #     return AnthropicExtractor()
    return DemoExtractor()
