"""tests for drg.engine — end-to-end DRG grouping."""

import pytest

from drg.engine import MSDRGEngine
from drg.schemas import ComplicationLevel, PartitionType


@pytest.fixture(scope="module")
def engine():
    return MSDRGEngine()


# ------------------------------------------------------------------
# basic grouping
# ------------------------------------------------------------------

class TestBasicGrouping:
    def test_ami_no_cc(self, engine):
        r = engine.group("I2109")
        assert r.drg_code == "282"
        assert r.mdc == "05"
        assert r.complication_level == ComplicationLevel.NONE
        assert r.partition == PartitionType.MEDICAL

    def test_ami_with_mcc(self, engine):
        r = engine.group("I2109", secondary_dxs=["J9601"])
        assert r.drg_code == "280"
        assert r.complication_level == ComplicationLevel.MCC

    def test_copd(self, engine):
        r = engine.group("J449")
        assert r.drg_code in ("190", "191", "192")
        assert r.mdc == "04"

    def test_pneumonia(self, engine):
        r = engine.group("J189")
        assert r.drg_code in ("193", "194", "195")

    def test_heart_failure(self, engine):
        r = engine.group("I5021")
        assert r.drg_code in ("291", "292", "293")


# ------------------------------------------------------------------
# surgical partition
# ------------------------------------------------------------------

class TestSurgicalPartition:
    def test_cardiac_stent_surgical(self, engine):
        r = engine.group("I2109", procedures=["02703DZ"])
        assert r.partition == PartitionType.SURGICAL
        assert r.has_or_procedure is True

    def test_no_procedure_medical(self, engine):
        r = engine.group("I2109")
        assert r.partition == PartitionType.MEDICAL
        assert r.has_or_procedure is False


# ------------------------------------------------------------------
# pre-MDC
# ------------------------------------------------------------------

class TestPreMDC:
    def test_heart_transplant(self, engine):
        # 02YA0Z0 = heart transplant
        r = engine.group("I5021", procedures=["02YA0Z0"])
        assert r.is_pre_mdc is True
        assert r.drg_code in ("001", "002")
        assert r.mdc == "PRE"

    def test_ecmo(self, engine):
        # 5A15223 = ECMO
        r = engine.group("J9601", procedures=["5A15223"])
        assert r.is_pre_mdc is True
        assert r.drg_code == "003"

    def test_lung_transplant(self, engine):
        # 0BYC0Z0 = lung transplant
        r = engine.group("J9601", procedures=["0BYC0Z0"])
        assert r.is_pre_mdc is True
        assert r.drg_code == "007"


# ------------------------------------------------------------------
# input echo
# ------------------------------------------------------------------

class TestInputEcho:
    def test_principal_dx_echoed(self, engine):
        r = engine.group("I2109")
        assert r.principal_diagnosis is not None
        assert r.principal_diagnosis.code == "I2109"
        assert r.principal_diagnosis.is_principal is True

    def test_secondary_dx_echoed(self, engine):
        r = engine.group("I2109", secondary_dxs=["E1165", "I10"])
        assert len(r.secondary_diagnoses) == 2
        codes = [d.code for d in r.secondary_diagnoses]
        assert "E1165" in codes
        assert "I10" in codes

    def test_encounter_echoed(self, engine):
        r = engine.group("I2109", age=55, sex="F")
        assert r.encounter.age == 55
        assert r.encounter.sex.value == "F"

    def test_weight_populated(self, engine):
        r = engine.group("I2109")
        assert r.weight > 0

    def test_description_populated(self, engine):
        r = engine.group("I2109")
        assert len(r.description) > 0


# ------------------------------------------------------------------
# edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    def test_dot_in_code(self, engine):
        r = engine.group("I21.09")
        assert r.drg_code == "282"

    def test_lowercase_code(self, engine):
        r = engine.group("i2109")
        assert r.drg_code == "282"
