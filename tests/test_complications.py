"""tests for drg.complications — CC/MCC resolution and exclusion logic."""

import pytest

from drg.complications import ComplicationResolver
from drg.schemas import ComplicationLevel


@pytest.fixture(scope="module")
def resolver():
    r = ComplicationResolver()
    r.load()
    return r


class TestLoading:
    def test_loads_without_error(self, resolver):
        assert resolver.exclusion_count() >= 0

    def test_has_exclusions(self, resolver):
        # cc_exclusions.txt is ~209K lines, should parse into real data
        assert resolver.exclusion_count() > 0


class TestIsCC:
    def test_known_mcc(self, resolver):
        # J9601 — acute respiratory failure with hypoxia — is MCC
        assert resolver.is_mcc("J9601") is True

    def test_mcc_not_cc(self, resolver):
        # MCC codes should not count as CC
        if resolver.is_mcc("J9601"):
            assert resolver.is_cc("J9601") is False

    def test_unknown_code(self, resolver):
        assert resolver.is_cc("ZZZZZ") is False
        assert resolver.is_mcc("ZZZZZ") is False


class TestResolve:
    def test_no_secondary_gives_none(self, resolver):
        level, cc, mcc = resolver.resolve("I2109", [], "01")
        assert level == ComplicationLevel.NONE
        assert cc == []
        assert mcc == []

    def test_mcc_secondary(self, resolver):
        # J9601 is MCC — should elevate to MCC level
        level, cc, mcc = resolver.resolve("I2109", ["J9601"], "01")
        assert level == ComplicationLevel.MCC
        assert "J9601" in mcc

    def test_dot_handling(self, resolver):
        # dots should be stripped automatically
        level1, _, _ = resolver.resolve("I21.09", ["J96.01"], "01")
        level2, _, _ = resolver.resolve("I2109", ["J9601"], "01")
        assert level1 == level2

    def test_case_insensitive(self, resolver):
        level1, _, _ = resolver.resolve("i2109", ["j9601"], "01")
        level2, _, _ = resolver.resolve("I2109", ["J9601"], "01")
        assert level1 == level2
