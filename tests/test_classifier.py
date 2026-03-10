"""tests for drg.classifier — MDC classification from principal diagnosis."""

import pytest

from drg.classifier import MDCClassifier, _in_range


@pytest.fixture(scope="module")
def classifier():
    c = MDCClassifier()
    c.load()
    return c


# ------------------------------------------------------------------
# range helper
# ------------------------------------------------------------------

class TestInRange:
    def test_exact_match(self):
        assert _in_range("I50", "I50", "I50") is True

    def test_subcode_included(self):
        assert _in_range("I5021", "I50", "I50") is True

    def test_below_range(self):
        assert _in_range("I49", "I50", "I50") is False

    def test_above_range(self):
        assert _in_range("I51", "I50", "I50") is False

    def test_multi_char_range(self):
        assert _in_range("I2109", "I00", "I99") is True

    def test_alpha_range_boundary(self):
        assert _in_range("G99", "G00", "G99") is True
        assert _in_range("H00", "G00", "G99") is False


# ------------------------------------------------------------------
# classification
# ------------------------------------------------------------------

class TestClassify:
    def test_circulatory_ami(self, classifier):
        mdc, desc = classifier.classify("I2109")
        assert mdc == "05"

    def test_respiratory(self, classifier):
        mdc, _ = classifier.classify("J449")
        assert mdc == "04"

    def test_nervous_system(self, classifier):
        mdc, _ = classifier.classify("G409")
        assert mdc == "01"

    def test_pregnancy(self, classifier):
        mdc, _ = classifier.classify("O80")
        assert mdc == "14"

    def test_newborn(self, classifier):
        mdc, _ = classifier.classify("Z3800")
        assert mdc == "15"

    def test_hiv(self, classifier):
        mdc, _ = classifier.classify("B20")
        assert mdc == "25"

    def test_empty_code(self, classifier):
        mdc, desc = classifier.classify("")
        assert mdc == "00"
        assert desc == "unassigned"

    def test_unrecognized_code(self, classifier):
        mdc, desc = classifier.classify("Q999")
        # Q codes (congenital) may not have explicit range — should get something
        assert isinstance(mdc, str)

    def test_dot_stripped(self, classifier):
        mdc1, _ = classifier.classify("I21.09")
        mdc2, _ = classifier.classify("I2109")
        assert mdc1 == mdc2

    def test_case_insensitive(self, classifier):
        mdc1, _ = classifier.classify("i2109")
        mdc2, _ = classifier.classify("I2109")
        assert mdc1 == mdc2


class TestDescription:
    def test_known_mdc(self, classifier):
        desc = classifier.description("05")
        assert "Circulatory" in desc

    def test_unknown_mdc(self, classifier):
        assert classifier.description("99") == ""
