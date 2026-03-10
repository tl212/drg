"""tests for drg.schemas — enums, pydantic models, validation."""

import pytest
from pydantic import ValidationError

from drg.schemas import (
    ComplicationLevel,
    Diagnosis,
    Encounter,
    GroupingResult,
    PartitionType,
    POAStatus,
    Procedure,
    Sex,
)

# ------------------------------------------------------------------
# enums
# ------------------------------------------------------------------

class TestEnums:
    def test_sex_values(self):
        assert Sex.MALE.value == "M"
        assert Sex.FEMALE.value == "F"
        assert Sex.UNKNOWN.value == "U"

    def test_complication_level_values(self):
        assert ComplicationLevel.MCC.value == "MCC"
        assert ComplicationLevel.CC.value == "CC"
        assert ComplicationLevel.NONE.value == "None"

    def test_partition_type_values(self):
        assert PartitionType.SURGICAL.value == "SURG"
        assert PartitionType.MEDICAL.value == "MED"

    def test_poa_status_values(self):
        assert POAStatus.YES.value == "Y"
        assert POAStatus.NO.value == "N"
        assert POAStatus.EXEMPT.value == "1"


# ------------------------------------------------------------------
# diagnosis
# ------------------------------------------------------------------

class TestDiagnosis:
    def test_basic_creation(self):
        dx = Diagnosis(code="I2109")
        assert dx.code == "I2109"
        assert dx.is_principal is False
        assert dx.poa_status == POAStatus.YES

    def test_principal_flag(self):
        dx = Diagnosis(code="I2109", is_principal=True)
        assert dx.is_principal is True

    def test_with_description(self):
        dx = Diagnosis(code="I2109", description="STEMI of unspecified site")
        assert dx.description == "STEMI of unspecified site"


# ------------------------------------------------------------------
# procedure
# ------------------------------------------------------------------

class TestProcedure:
    def test_basic_creation(self):
        proc = Procedure(code="02703ZZ")
        assert proc.code == "02703ZZ"
        assert proc.description is None

    def test_with_description(self):
        proc = Procedure(code="02703ZZ", description="Dilation of coronary artery")
        assert proc.description == "Dilation of coronary artery"


# ------------------------------------------------------------------
# encounter
# ------------------------------------------------------------------

class TestEncounter:
    def test_basic_creation(self):
        enc = Encounter(age=72, sex=Sex.MALE, discharge_status="01")
        assert enc.age == 72
        assert enc.sex == Sex.MALE

    def test_age_validation_lower(self):
        with pytest.raises(ValidationError):
            Encounter(age=-1, sex=Sex.MALE, discharge_status="01")

    def test_age_validation_upper(self):
        with pytest.raises(ValidationError):
            Encounter(age=125, sex=Sex.MALE, discharge_status="01")

    def test_age_boundary_valid(self):
        enc = Encounter(age=0, sex=Sex.FEMALE, discharge_status="01")
        assert enc.age == 0
        enc2 = Encounter(age=124, sex=Sex.FEMALE, discharge_status="01")
        assert enc2.age == 124


# ------------------------------------------------------------------
# grouping result
# ------------------------------------------------------------------

class TestGroupingResult:
    def test_minimal_creation(self):
        result = GroupingResult(
            drg_code="282",
            description="AMI DISCHARGED ALIVE WITHOUT CC/MCC",
            mdc="05",
            mdc_description="Circulatory",
            weight=0.72,
            partition=PartitionType.MEDICAL,
            complication_level=ComplicationLevel.NONE,
        )
        assert result.drg_code == "282"
        assert result.is_pre_mdc is False
        assert result.has_or_procedure is False
        assert result.cc_codes_applied == []
        assert result.mcc_codes_applied == []

    def test_with_input_echo(self):
        pdx = Diagnosis(code="I2109", is_principal=True)
        result = GroupingResult(
            drg_code="280",
            description="AMI WITH MCC",
            mdc="05",
            mdc_description="Circulatory",
            weight=1.5,
            partition=PartitionType.MEDICAL,
            complication_level=ComplicationLevel.MCC,
            principal_diagnosis=pdx,
            mcc_codes_applied=["J9601"],
        )
        assert result.principal_diagnosis.code == "I2109"
        assert result.mcc_codes_applied == ["J9601"]
