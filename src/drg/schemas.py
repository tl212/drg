"""pydantic models and enums for MS-DRG grouping."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Sex(str, Enum):
    """patient sex."""
    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"


class ComplicationLevel(str, Enum):
    """CC/MCC complication level for severity adjustment."""
    MCC = "MCC"
    CC = "CC"
    NONE = "None"


class PartitionType(str, Enum):
    """surgical or medical partition."""
    SURGICAL = "SURG"
    MEDICAL = "MED"


class POAStatus(str, Enum):
    """present on admission indicator."""
    YES = "Y"              # present at time of inpatient admission
    NO = "N"               # not present at time of inpatient admission
    UNKNOWN = "U"          # documentation insufficient to determine
    UNDETERMINED = "W"     # provider unable to clinically determine
    EXEMPT = "1"           # exempt from POA reporting


class Diagnosis(BaseModel):
    """ICD-10-CM diagnosis code."""
    code: str = Field(..., description="ICD-10-CM code without dots (e.g. 'I2109')")
    description: Optional[str] = None
    is_principal: bool = False
    poa_status: POAStatus = POAStatus.YES


class Procedure(BaseModel):
    """ICD-10-PCS procedure code."""
    code: str = Field(..., description="ICD-10-PCS 7-character code (e.g. '02703Z4')")
    description: Optional[str] = None


class Encounter(BaseModel):
    """patient demographics for DRG grouping."""
    age: int = Field(..., ge=0, le=124, description="patient age in years")
    sex: Sex = Field(..., description="patient sex")
    discharge_status: str = Field(
        ...,
        description="discharge status code (01=home, 02=short-term hospital, etc.)",
    )


class GroupingResult(BaseModel):
    """output of MS-DRG grouping."""
    drg_code: str = Field(..., description="MS-DRG code (e.g. '246')")
    description: str = Field(..., description="MS-DRG description")
    mdc: str = Field(..., description="major diagnostic category code (e.g. '05')")
    mdc_description: str = Field(..., description="MDC description")
    weight: float = Field(..., description="DRG relative weight for payment calculation")
    geometric_los: Optional[float] = Field(None, description="geometric mean length of stay")
    arithmetic_los: Optional[float] = Field(None, description="arithmetic mean length of stay")
    partition: PartitionType = Field(..., description="surgical or medical partition")
    complication_level: ComplicationLevel = Field(..., description="CC/MCC complication level")
    is_pre_mdc: bool = Field(False, description="true if pre-MDC assignment (transplants, ECMO)")

    # input echo — transparency into what drove the grouping
    principal_diagnosis: Optional[Diagnosis] = None
    secondary_diagnoses: list[Diagnosis] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    encounter: Optional[Encounter] = None

    # complication detail
    has_or_procedure: bool = Field(False, description="true if OR procedure present")
    cc_codes_applied: list[str] = Field(
        default_factory=list, description="CC codes that contributed to complication level",
    )
    mcc_codes_applied: list[str] = Field(
        default_factory=list, description="MCC codes that contributed to complication level",
    )
