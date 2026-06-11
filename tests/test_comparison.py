"""Tests for the deterministic comparison rules.

These map directly to the acceptance criteria in the spec:
- brand-name case differences match (STONE'S THROW vs Stone's Throw)
- the Government Warning is strict (title case → mismatch)
- unreadable fields become NEEDS_REVIEW, never a guess
"""

from app.models import FieldStatus
from app.services.comparison import (
    GOVERNMENT_WARNING_TEXT,
    compare_alcohol_content,
    compare_government_warning,
    compare_net_contents,
    compare_text_field,
)


class TestBrandName:
    def test_exact_match(self):
        r = compare_text_field("brand_name", "Brand name", "OLD TOM DISTILLERY", "OLD TOM DISTILLERY")
        assert r.status == FieldStatus.MATCH
        assert r.note is None

    def test_case_difference_is_match_with_note(self):
        r = compare_text_field("brand_name", "Brand name", "Stone's Throw", "STONE'S THROW")
        assert r.status == FieldStatus.MATCH
        assert "formatting" in r.note

    def test_different_brand_is_mismatch(self):
        r = compare_text_field("brand_name", "Brand name", "Stone's Throw", "River Bend")
        assert r.status == FieldStatus.MISMATCH

    def test_missing_field_needs_review(self):
        r = compare_text_field("brand_name", "Brand name", "Stone's Throw", None)
        assert r.status == FieldStatus.NEEDS_REVIEW


class TestAlcoholContent:
    def test_match_with_proof(self):
        r = compare_alcohol_content("45% Alc./Vol. (90 Proof)", "45% Alc/Vol 90 PROOF")
        assert r.status == FieldStatus.MATCH

    def test_abv_format_variants_match(self):
        r = compare_alcohol_content("6.8% Alc./Vol.", "6.8% ABV")
        assert r.status == FieldStatus.MATCH

    def test_wrong_abv_is_mismatch(self):
        r = compare_alcohol_content("45% Alc./Vol.", "40% Alc./Vol.")
        assert r.status == FieldStatus.MISMATCH

    def test_inconsistent_proof_is_mismatch(self):
        r = compare_alcohol_content("45% Alc./Vol. (90 Proof)", "45% Alc./Vol. (80 Proof)")
        assert r.status == FieldStatus.MISMATCH

    def test_proof_only_label_derives_abv(self):
        r = compare_alcohol_content("40% Alc./Vol.", "80 Proof")
        assert r.status == FieldStatus.MATCH


class TestNetContents:
    def test_format_variants_match(self):
        r = compare_net_contents("750 mL", "750ml")
        assert r.status == FieldStatus.MATCH

    def test_liters_normalized(self):
        r = compare_net_contents("1 L", "1000 mL")
        assert r.status == FieldStatus.MATCH

    def test_different_volume_is_mismatch(self):
        r = compare_net_contents("750 mL", "700 mL")
        assert r.status == FieldStatus.MISMATCH


class TestGovernmentWarning:
    def test_exact_statutory_text_matches(self):
        r = compare_government_warning(GOVERNMENT_WARNING_TEXT)
        assert r.status == FieldStatus.MATCH

    def test_title_case_heading_is_mismatch(self):
        bad = GOVERNMENT_WARNING_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
        r = compare_government_warning(bad)
        assert r.status == FieldStatus.MISMATCH
        assert "capital letters" in r.note

    def test_altered_wording_is_mismatch(self):
        bad = GOVERNMENT_WARNING_TEXT.replace("birth defects", "health issues")
        r = compare_government_warning(bad)
        assert r.status == FieldStatus.MISMATCH

    def test_missing_warning_is_mismatch(self):
        r = compare_government_warning(None)
        assert r.status == FieldStatus.MISMATCH

    def test_extra_whitespace_is_tolerated(self):
        spaced = GOVERNMENT_WARNING_TEXT.replace(" ", "  ")
        r = compare_government_warning(spaced)
        assert r.status == FieldStatus.MATCH


class TestDemoExtractor:
    """The demo extractor must produce the intended outcome for each sample label."""

    def setup_method(self):
        from app.services.extraction import DemoExtractor
        self.extractor = DemoExtractor()

    def test_wrong_abv_sample_extracts_wrong_abv(self):
        result = self.extractor.extract(b"", "image/png", filename="label_04_wrong_abv_mismatch.png")
        assert result.alcohol_content == "40% Alc./Vol. (80 Proof)"

    def test_title_case_sample_extracts_title_case_warning(self):
        result = self.extractor.extract(b"", "image/png", filename="label_02_title_case_warning_mismatch.png")
        assert result.government_warning.startswith("Government Warning:")

    def test_blurry_sample_is_unreadable(self):
        result = self.extractor.extract(b"", "image/png", filename="label_06_blurry_unreadable.png")
        assert result.readable is False

    def test_missing_warning_sample_has_no_warning(self):
        result = self.extractor.extract(b"", "image/png", filename="label_05_missing_warning_wrong_volume.png")
        assert result.government_warning is None

    def test_unknown_image_falls_back_to_sample_with_note(self):
        result = self.extractor.extract(b"", "image/png", filename="my_photo.png")
        assert result.brand_name == "OLD TOM DISTILLERY"
        assert "not actually read" in result.notes
