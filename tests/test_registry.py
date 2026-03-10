"""tests for drg.registry — code lookups and data loading."""

import pytest

from drg.registry import CodeRegistry


@pytest.fixture(scope="module")
def registry():
    reg = CodeRegistry()
    reg.load()
    return reg


class TestDataLoading:
    def test_diagnoses_loaded(self, registry):
        assert registry.diagnosis_count() > 0

    def test_drg_table_loaded(self, registry):
        assert registry.drg_count() > 0


class TestDiagnosisLookup:
    def test_known_code(self, registry):
        desc = registry.lookup_diagnosis("I2109")
        assert desc is not None
        assert len(desc) > 0

    def test_unknown_code(self, registry):
        assert registry.lookup_diagnosis("ZZZZZ") is None

    def test_dot_stripped(self, registry):
        desc_no_dot = registry.lookup_diagnosis("I2109")
        desc_dot = registry.lookup_diagnosis("I21.09")
        assert desc_no_dot == desc_dot


class TestProcedureLookup:
    def test_known_pcs(self, registry):
        desc = registry.lookup_procedure("02703ZZ")
        # may or may not be in tuva data — just check no crash
        assert desc is None or isinstance(desc, str)


class TestDRGLookup:
    def test_known_drg(self, registry):
        ref = registry.lookup_drg("282")
        assert ref is not None
        assert ref.drg_code == "282"
        assert ref.weight > 0

    def test_zero_padded(self, registry):
        ref = registry.lookup_drg("1")
        assert ref is not None
        assert ref.drg_code == "001"

    def test_unknown_drg(self, registry):
        assert registry.lookup_drg("000") is None

    def test_drg_has_mdc(self, registry):
        ref = registry.lookup_drg("282")
        assert ref.mdc in ("05", "PRE")


class TestFindDRGsForMDC:
    def test_mdc_05_surgical(self, registry):
        hits = registry.find_drgs_for_mdc("05", "SURG")
        assert len(hits) > 0
        assert all(h.mdc == "05" for h in hits)

    def test_mdc_05_medical(self, registry):
        hits = registry.find_drgs_for_mdc("05", "MED")
        assert len(hits) > 0

    def test_nonexistent_mdc(self, registry):
        hits = registry.find_drgs_for_mdc("99")
        assert hits == []


class TestORProcedure:
    def test_open_bypass_is_or(self, registry):
        # coronary bypass, open approach
        assert registry.is_or_procedure("0210093") is True

    def test_percutaneous_cardiac_is_or(self, registry):
        # percutaneous coronary dilation
        assert registry.is_or_procedure("02703ZZ") is True

    def test_short_code_not_or(self, registry):
        assert registry.is_or_procedure("027") is False

    def test_ecmo_is_or(self, registry):
        # ECMO — section 5
        assert registry.is_or_procedure("5A15223") is True
