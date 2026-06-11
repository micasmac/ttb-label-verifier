"""Deterministic field comparison.

The AI extracts text from the label image; the rules in this module decide
match vs. mismatch. Keeping comparison out of the model means the strict
checks (especially the Government Warning) are predictable and testable.

Matching philosophy from the discovery interviews:
- Trivial formatting differences are NOT mismatches ("STONE'S THROW" vs
  "Stone's Throw" is the same brand) — they match with a note.
- The Government Warning gets zero tolerance: exact statutory wording, and
  "GOVERNMENT WARNING:" must be in all caps.
- When the extractor couldn't read a field, the result is NEEDS_REVIEW,
  never a guess.
"""

from __future__ import annotations

import re
import unicodedata

from ..models import ExtractedLabel, FieldResult, FieldStatus

# 27 CFR Part 16 — mandatory health warning statement.
GOVERNMENT_WARNING_TEXT = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should "
    "not drink alcoholic beverages during pregnancy because of the risk of "
    "birth defects. (2) Consumption of alcoholic beverages impairs your "
    "ability to drive a car or operate machinery, and may cause health "
    "problems."
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _normalize_loose(text: str) -> str:
    """Casefold, strip punctuation, collapse whitespace. For brand/class fields."""
    text = unicodedata.normalize("NFKD", text)
    text = _PUNCT_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip().casefold()


def _normalize_ws(text: str) -> str:
    """Collapse whitespace only — preserves case and punctuation."""
    return _WS_RE.sub(" ", text).strip()


def _parse_abv(text: str) -> float | None:
    """Pull the ABV percentage out of strings like '45% Alc./Vol. (90 Proof)'."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return float(match.group(1)) if match else None


def _parse_proof(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*proof", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


_UNIT_TO_ML = {
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "cl": 10.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "litre": 1000.0,
    "litres": 1000.0,
    "oz": 29.5735,
    "floz": 29.5735,
}


def _parse_volume_ml(text: str) -> float | None:
    """Normalize net contents to milliliters. '750 mL', '750ml', '1 L' → mL."""
    cleaned = text.replace("fl.", "fl").replace("fl ", "fl")
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(ml|cl|l|liters?|litres?|milliliters?|floz|oz)\b",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).casefold().replace(" ", "")
    return value * _UNIT_TO_ML.get(unit, 0) or None


def _unreadable(field: str, label: str, app_value: str) -> FieldResult:
    return FieldResult(
        field=field,
        label=label,
        status=FieldStatus.NEEDS_REVIEW,
        application_value=app_value,
        extracted_value=None,
        note="Could not be read from the label image. Verify by eye or request a clearer image.",
    )


def compare_text_field(field: str, label: str, app_value: str, extracted: str | None) -> FieldResult:
    """Loose comparison for brand name and class/type."""
    if not extracted:
        return _unreadable(field, label, app_value)

    if _normalize_ws(app_value) == _normalize_ws(extracted):
        status, note = FieldStatus.MATCH, None
    elif _normalize_loose(app_value) == _normalize_loose(extracted):
        status = FieldStatus.MATCH
        note = "Matches with a minor formatting difference (capitalization or punctuation)."
    else:
        status, note = FieldStatus.MISMATCH, None

    return FieldResult(
        field=field,
        label=label,
        status=status,
        application_value=app_value,
        extracted_value=extracted,
        note=note,
    )


def compare_alcohol_content(app_value: str, extracted: str | None) -> FieldResult:
    field, label = "alcohol_content", "Alcohol content"
    if not extracted:
        return _unreadable(field, label, app_value)

    app_abv = _parse_abv(app_value)
    label_abv = _parse_abv(extracted)
    label_proof = _parse_proof(extracted)

    # Label might state proof only — derive ABV from it.
    if label_abv is None and label_proof is not None:
        label_abv = label_proof / 2

    if app_abv is None or label_abv is None:
        return FieldResult(
            field=field, label=label, status=FieldStatus.NEEDS_REVIEW,
            application_value=app_value, extracted_value=extracted,
            note="Could not parse a percentage from one of the values.",
        )

    if abs(app_abv - label_abv) > 0.05:
        return FieldResult(
            field=field, label=label, status=FieldStatus.MISMATCH,
            application_value=app_value, extracted_value=extracted,
            note=f"Application states {app_abv}% ABV but the label reads {label_abv}%.",
        )

    # ABV matches — sanity-check proof if the label states one.
    if label_proof is not None and abs(label_proof - label_abv * 2) > 0.1:
        return FieldResult(
            field=field, label=label, status=FieldStatus.MISMATCH,
            application_value=app_value, extracted_value=extracted,
            note=f"Proof on the label ({label_proof}) does not equal 2 × ABV ({label_abv}%).",
        )

    return FieldResult(
        field=field, label=label, status=FieldStatus.MATCH,
        application_value=app_value, extracted_value=extracted,
    )


def compare_net_contents(app_value: str, extracted: str | None) -> FieldResult:
    field, label = "net_contents", "Net contents"
    if not extracted:
        return _unreadable(field, label, app_value)

    app_ml = _parse_volume_ml(app_value)
    label_ml = _parse_volume_ml(extracted)

    if app_ml is None or label_ml is None:
        return FieldResult(
            field=field, label=label, status=FieldStatus.NEEDS_REVIEW,
            application_value=app_value, extracted_value=extracted,
            note="Could not parse a volume from one of the values.",
        )

    status = FieldStatus.MATCH if abs(app_ml - label_ml) < 0.5 else FieldStatus.MISMATCH
    return FieldResult(
        field=field, label=label, status=status,
        application_value=app_value, extracted_value=extracted,
    )


def compare_government_warning(extracted: str | None) -> FieldResult:
    """Strict, zero-tolerance check against the statutory text."""
    field, label = "government_warning", "Government warning"
    required = GOVERNMENT_WARNING_TEXT
    if not extracted:
        return FieldResult(
            field=field, label=label, status=FieldStatus.MISMATCH,
            application_value=required, extracted_value=None,
            note="No Government Warning statement was found on the label.",
        )

    extracted_norm = _normalize_ws(extracted)

    if not extracted_norm.startswith("GOVERNMENT WARNING:"):
        prefix = extracted_norm[:20]
        return FieldResult(
            field=field, label=label, status=FieldStatus.MISMATCH,
            application_value=required, extracted_value=extracted,
            note=f'"GOVERNMENT WARNING:" must appear in all capital letters. The label shows "{prefix}…".',
        )

    if extracted_norm != required:
        return FieldResult(
            field=field, label=label, status=FieldStatus.MISMATCH,
            application_value=required, extracted_value=extracted,
            note="Wording does not match the statutory text word-for-word.",
        )

    return FieldResult(
        field=field, label=label, status=FieldStatus.MATCH,
        application_value=required, extracted_value=extracted,
        note="Bold formatting cannot be reliably confirmed from an image — verify visually if in doubt.",
    )


def compare_all(application: dict, extracted: ExtractedLabel) -> list[FieldResult]:
    return [
        compare_text_field("brand_name", "Brand name", application["brand_name"], extracted.brand_name),
        compare_text_field("class_type", "Class / type", application["class_type"], extracted.class_type),
        compare_alcohol_content(application["alcohol_content"], extracted.alcohol_content),
        compare_net_contents(application["net_contents"], extracted.net_contents),
        compare_government_warning(extracted.government_warning),
    ]


def summarize(results: list[FieldResult]) -> str:
    total = len(results)
    matches = sum(r.status == FieldStatus.MATCH for r in results)
    mismatches = [r.label for r in results if r.status == FieldStatus.MISMATCH]
    reviews = [r.label for r in results if r.status == FieldStatus.NEEDS_REVIEW]

    if matches == total:
        return f"All {total} fields match."
    parts = [f"{matches} of {total} fields match"]
    if mismatches:
        parts.append("mismatch: " + ", ".join(mismatches))
    if reviews:
        parts.append("needs review: " + ", ".join(reviews))
    return " — ".join(parts) + "."
