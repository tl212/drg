"""MS-DRG grouping engine — main entry point for DRG assignment."""

from typing import Optional

from drg.classifier import MDCClassifier
from drg.complications import ComplicationResolver
from drg.registry import CodeRegistry
from drg.schemas import (
    ComplicationLevel,
    Diagnosis,
    Encounter,
    GroupingResult,
    PartitionType,
    Procedure,
    Sex,
)


class MSDRGEngine:
    """assigns MS-DRG codes from diagnoses, procedures, and demographics.

    usage:
        engine = MSDRGEngine()
        result = engine.group(
            principal_dx="I2109",
            secondary_dxs=["E1165", "I10"],
            procedures=["02703ZZ"],
        )
    """

    def __init__(self) -> None:
        self._registry = CodeRegistry()
        self._resolver = ComplicationResolver()
        self._classifier = MDCClassifier()
        self._loaded = False

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    def group(
        self,
        principal_dx: str,
        secondary_dxs: Optional[list[str]] = None,
        procedures: Optional[list[str]] = None,
        age: int = 65,
        sex: str = "M",
        discharge_status: str = "01",
    ) -> GroupingResult:
        """assign an MS-DRG for an inpatient encounter.

        args:
            principal_dx: ICD-10-CM code (dots optional)
            secondary_dxs: secondary ICD-10-CM codes
            procedures: ICD-10-PCS codes
            age: patient age in years
            sex: patient sex (M/F/U)
            discharge_status: discharge status code

        returns:
            GroupingResult with assigned DRG and supporting detail
        """
        self._boot()

        secondary_dxs = secondary_dxs or []
        procedures = procedures or []

        # build typed objects
        encounter = Encounter(age=age, sex=Sex(sex), discharge_status=discharge_status)

        pdx = self._build_diagnosis(principal_dx, is_principal=True)
        sdxs = [self._build_diagnosis(c, is_principal=False) for c in secondary_dxs]
        procs = [self._build_procedure(c) for c in procedures]

        # step 1 — pre-MDC (transplants, ECMO, tracheostomy)
        pre = self._evaluate_pre_mdc(pdx, procs, encounter, sdxs)
        if pre:
            return pre

        # step 2 — MDC from principal dx
        mdc_code, mdc_desc = self._classifier.classify(pdx.code)

        # step 3 — surgical / medical partition
        has_or, partition = self._partition(procs)

        # step 4 — complication severity
        comp_level, cc_list, mcc_list = self._resolver.resolve(
            pdx.code,
            [d.code for d in sdxs],
            encounter.discharge_status,
        )

        # step 5 — final DRG
        drg_code, drg_desc, wt, geo, arith = self._select_drg(
            mdc_code, partition, comp_level, has_or, procs, encounter, pdx.code,
        )

        return GroupingResult(
            drg_code=drg_code,
            description=drg_desc,
            mdc=mdc_code,
            mdc_description=mdc_desc,
            weight=wt,
            geometric_los=geo,
            arithmetic_los=arith,
            partition=partition,
            complication_level=comp_level,
            is_pre_mdc=False,
            principal_diagnosis=pdx,
            secondary_diagnoses=sdxs,
            procedures=procs,
            encounter=encounter,
            has_or_procedure=has_or,
            cc_codes_applied=cc_list,
            mcc_codes_applied=mcc_list,
        )

    # ------------------------------------------------------------------
    # bootstrap
    # ------------------------------------------------------------------

    def _boot(self) -> None:
        """lazy-load all reference data on first call."""
        if self._loaded:
            return
        self._registry.load()
        self._resolver.load()
        self._classifier.load()
        self._loaded = True

    # ------------------------------------------------------------------
    # object builders
    # ------------------------------------------------------------------

    @staticmethod
    def _norm(code: str) -> str:
        return code.replace(".", "").upper().strip()

    def _build_diagnosis(self, raw: str, *, is_principal: bool) -> Diagnosis:
        code = self._norm(raw)
        return Diagnosis(
            code=code,
            description=self._registry.lookup_diagnosis(code),
            is_principal=is_principal,
        )

    def _build_procedure(self, raw: str) -> Procedure:
        code = self._norm(raw)
        return Procedure(
            code=code,
            description=self._registry.lookup_procedure(code),
        )

    # ------------------------------------------------------------------
    # step 1 — pre-MDC
    # ------------------------------------------------------------------

    def _evaluate_pre_mdc(
        self,
        pdx: Diagnosis,
        procs: list[Procedure],
        encounter: Encounter,
        sdxs: list[Diagnosis],
    ) -> Optional[GroupingResult]:
        """check for pre-MDC DRGs 001-019 (transplants, ECMO, trach, CAR-T)."""
        proc_codes = [p.code for p in procs]

        # resolve complications for severity splits within pre-MDC
        comp_level, cc_list, mcc_list = self._resolver.resolve(
            pdx.code, [d.code for d in sdxs], encounter.discharge_status,
        )
        has_mcc = comp_level == ComplicationLevel.MCC
        has_cc = comp_level == ComplicationLevel.CC

        drg: Optional[str] = None

        for code in proc_codes:
            if len(code) != 7:
                continue

            sec, bsys, rop = code[0], code[1], code[2]
            bpart = code[3]

            # heart transplant / heart assist (001-002)
            if sec == "0" and bsys == "2" and rop == "Y" and bpart == "A":
                drg = "001" if has_mcc else "002"
                break
            if sec == "0" and bsys == "2" and rop == "H" and code[5] in ("Q", "R", "S"):
                drg = "001" if has_mcc else "002"
                break

            # liver transplant (005-006)
            if sec == "0" and bsys == "F" and rop == "Y" and bpart != "G":
                drg = "005" if has_mcc else "006"
                break

            # pancreas transplant — check for simultaneous kidney (008 vs 010)
            if sec == "0" and bsys == "F" and rop == "Y" and bpart == "G":
                has_kidney = any(
                    c[0:3] == "0TY" for c in proc_codes if len(c) >= 3
                )
                drg = "008" if has_kidney else "010"
                break

            # kidney transplant (needs pancreas check for 008)
            if sec == "0" and bsys == "T" and rop == "Y":
                has_pancreas = any(
                    len(c) >= 4 and c[0:3] == "0FY" and c[3] == "G"
                    for c in proc_codes
                )
                if has_pancreas:
                    drg = "008"
                break

            # lung transplant (007)
            if sec == "0" and bsys == "B" and rop == "Y":
                drg = "007"
                break

            # tracheostomy (003-004 or 011-013)
            if sec == "0" and bsys == "B" and rop == "1" and bpart == "1":
                if self._is_face_mouth_neck_dx(pdx.code):
                    drg = "011" if has_mcc else ("012" if has_cc else "013")
                else:
                    drg = "003" if has_mcc else "004"
                break

            # ECMO (003)
            if sec == "5" and bsys == "A" and rop == "1" and bpart == "5":
                drg = "003"
                break

            # bone marrow / stem cell transplant (014, 016-017)
            if sec == "3" and bsys == "0" and rop == "2" and code[5] in ("G", "X"):
                drg = "014"
                break

        if drg is None:
            return None

        ref = self._registry.lookup_drg(drg)
        return GroupingResult(
            drg_code=drg,
            description=ref.description if ref else "pre-MDC",
            mdc="PRE",
            mdc_description="pre-MDC",
            weight=ref.weight if ref else 0.0,
            geometric_los=ref.geometric_los if ref else None,
            arithmetic_los=ref.arithmetic_los if ref else None,
            partition=PartitionType.SURGICAL,
            complication_level=comp_level,
            is_pre_mdc=True,
            principal_diagnosis=pdx,
            secondary_diagnoses=sdxs,
            procedures=procs,
            encounter=encounter,
            has_or_procedure=True,
            cc_codes_applied=cc_list,
            mcc_codes_applied=mcc_list,
        )

    @staticmethod
    def _is_face_mouth_neck_dx(code: str) -> bool:
        """heuristic: principal dx relates to face, mouth, or neck."""
        return code.startswith(("J", "K")) or code.startswith(("C0", "C1", "D0", "D1"))

    # ------------------------------------------------------------------
    # step 3 — partition
    # ------------------------------------------------------------------

    def _partition(
        self, procs: list[Procedure],
    ) -> tuple[bool, PartitionType]:
        """split encounter into surgical or medical based on OR procedures."""
        for p in procs:
            if self._registry.is_or_procedure(p.code):
                return True, PartitionType.SURGICAL
        return False, PartitionType.MEDICAL

    # ------------------------------------------------------------------
    # step 5 — DRG selection
    # ------------------------------------------------------------------

    def _select_drg(
        self,
        mdc: str,
        partition: PartitionType,
        comp: ComplicationLevel,
        has_or: bool,
        procs: list[Procedure],
        encounter: Encounter,
        pdx_code: str,
    ) -> tuple[str, str, float, Optional[float], Optional[float]]:
        """pick the final MS-DRG from MDC, partition, and complication level."""

        # surgical path — try procedure-specific family first
        if partition == PartitionType.SURGICAL and procs:
            hit = self._drg_from_procedure(mdc, procs, comp)
            if hit:
                return hit

        # medical path — try diagnosis-specific family
        if partition == PartitionType.MEDICAL and pdx_code:
            hit = self._drg_from_diagnosis(mdc, pdx_code, comp)
            if hit:
                return hit

        # fallback — scan all DRGs in this MDC + partition, match by severity keyword
        type_str = "SURG" if partition == PartitionType.SURGICAL else "MED"
        candidates = self._registry.find_drgs_for_mdc(mdc, type_str)
        if not candidates:
            return "999", "UNGROUPABLE", 0.0, None, None

        best = self._best_severity_match(candidates, comp)
        if best:
            return (
                best.drg_code, best.description, best.weight,
                best.geometric_los, best.arithmetic_los,
            )

        return "999", "UNGROUPABLE", 0.0, None, None

    # ------------------------------------------------------------------
    # diagnosis → DRG families
    # ------------------------------------------------------------------

    def _drg_from_diagnosis(
        self,
        mdc: str,
        pdx: str,
        comp: ComplicationLevel,
    ) -> Optional[tuple[str, str, float, Optional[float], Optional[float]]]:
        """map principal dx to a DRG family and apply severity split."""
        family = None

        if mdc == "04":
            family = self._respiratory_family(pdx)
        elif mdc == "05":
            family = self._circulatory_family(pdx)

        if family is None:
            return None

        return self._apply_three_way(family, comp)

    @staticmethod
    def _respiratory_family(dx: str) -> Optional[tuple[str, str, str, str]]:
        """(drg_mcc, drg_cc, drg_none, label) for respiratory diagnoses."""
        if dx.startswith(("J40", "J41", "J42", "J43", "J44", "J47")):
            return ("190", "191", "192", "CHRONIC OBSTRUCTIVE PULMONARY DISEASE")
        if dx.startswith("J45") or dx.startswith(("J20", "J21")):
            return ("202", "202", "203", "BRONCHITIS AND ASTHMA")
        if dx.startswith(("J12", "J13", "J14", "J15", "J16", "J17", "J18")):
            return ("193", "194", "195", "SIMPLE PNEUMONIA AND PLEURISY")
        if dx.startswith("I26"):
            return ("175", "176", "176", "PULMONARY EMBOLISM")
        if dx.startswith("J96"):
            return ("189", "189", "189", "PULMONARY EDEMA AND RESPIRATORY FAILURE")
        if dx.startswith(("J90", "J91")):
            return ("186", "187", "188", "PLEURAL EFFUSION")
        if dx.startswith("J93"):
            return ("199", "200", "201", "PNEUMOTHORAX")
        if dx.startswith("J84"):
            return ("196", "197", "198", "INTERSTITIAL LUNG DISEASE")
        if dx.startswith(("C33", "C34", "C38", "C39", "D02", "D14", "D38")):
            return ("180", "181", "182", "RESPIRATORY NEOPLASMS")
        if dx.startswith(("S22", "S27")):
            return ("183", "184", "185", "MAJOR CHEST TRAUMA")
        return None

    @staticmethod
    def _circulatory_family(dx: str) -> Optional[tuple[str, str, str, str]]:
        """(drg_mcc, drg_cc, drg_none, label) for circulatory diagnoses."""
        if dx.startswith(("I21", "I22")):
            return ("280", "281", "282", "ACUTE MYOCARDIAL INFARCTION")
        if dx.startswith("I50"):
            return ("291", "292", "293", "HEART FAILURE AND SHOCK")
        if dx.startswith(("I47", "I48", "I49")):
            return ("308", "309", "310", "CARDIAC ARRHYTHMIA AND CONDUCTION DISORDERS")
        if dx.startswith("R07"):
            return ("311", "312", "313", "ANGINA PECTORIS")
        if dx.startswith("R55"):
            return ("312", "312", "313", "SYNCOPE AND COLLAPSE")
        if dx.startswith(("I10", "I11", "I12", "I13", "I15", "I16")):
            return ("304", "305", "305", "HYPERTENSION")
        if dx.startswith("I25"):
            return ("302", "303", "303", "ATHEROSCLEROSIS")
        if dx.startswith("I71"):
            return ("299", "300", "301", "PERIPHERAL VASCULAR DISORDERS")
        return None

    # ------------------------------------------------------------------
    # procedure → DRG families (cardiac, MDC 05)
    # ------------------------------------------------------------------

    def _drg_from_procedure(
        self,
        mdc: str,
        procs: list[Procedure],
        comp: ComplicationLevel,
    ) -> Optional[tuple[str, str, float, Optional[float], Optional[float]]]:
        """map procedure codes to a DRG family and apply severity split."""
        for p in procs:
            code = p.code
            if len(code) != 7:
                continue

            if mdc == "05":
                family = self._cardiac_proc_family(code)
                if family:
                    return self._apply_two_way(family, comp)

        return None

    @staticmethod
    def _cardiac_proc_family(code: str) -> Optional[tuple[str, str, str]]:
        """(drg_mcc, drg_other, label) for cardiac procedures."""
        sec, bsys, rop = code[0], code[1], code[2]
        approach, device = code[4], code[5]

        # coronary stent / angioplasty (percutaneous dilation)
        if sec == "0" and bsys == "2" and rop == "7" and approach == "3":
            if device in ("D", "E", "T"):
                return (
                    "321", "322",
                    "PERCUTANEOUS CARDIOVASCULAR PROCEDURES WITH INTRALUMINAL DEVICE",
                )
            return (
                "250", "251",
                "PERCUTANEOUS CARDIOVASCULAR PROCEDURES WITHOUT INTRALUMINAL DEVICE",
            )

        # coronary bypass
        if sec == "0" and bsys == "2" and rop == "1":
            return ("235", "236", "CORONARY BYPASS WITHOUT CARDIAC CATHETERIZATION")

        # valve replacement
        if sec == "0" and bsys == "2" and rop == "R" and code[3] in ("F", "G", "H", "J"):
            return ("216", "220", "CARDIAC VALVE PROCEDURES")

        return None

    # ------------------------------------------------------------------
    # severity splits
    # ------------------------------------------------------------------

    def _apply_three_way(
        self,
        family: tuple[str, str, str, str],
        comp: ComplicationLevel,
    ) -> tuple[str, str, float, Optional[float], Optional[float]]:
        """pick DRG from a 3-way split (MCC / CC / none)."""
        mcc_drg, cc_drg, none_drg, label = family

        if comp == ComplicationLevel.MCC:
            code = mcc_drg
        elif comp == ComplicationLevel.CC:
            code = cc_drg
        else:
            code = none_drg

        return self._resolve_drg(code, label)

    def _apply_two_way(
        self,
        family: tuple[str, str, str],
        comp: ComplicationLevel,
    ) -> tuple[str, str, float, Optional[float], Optional[float]]:
        """pick DRG from a 2-way split (MCC / other)."""
        mcc_drg, other_drg, label = family
        code = mcc_drg if comp == ComplicationLevel.MCC else other_drg
        return self._resolve_drg(code, label)

    def _resolve_drg(
        self, code: str, fallback_desc: str,
    ) -> tuple[str, str, float, Optional[float], Optional[float]]:
        """look up DRG weights, falling back to label if not found."""
        ref = self._registry.lookup_drg(code)
        if ref:
            return ref.drg_code, ref.description, ref.weight, ref.geometric_los, ref.arithmetic_los
        return code, fallback_desc, 0.0, None, None

    # ------------------------------------------------------------------
    # fallback severity matching
    # ------------------------------------------------------------------

    @staticmethod
    def _best_severity_match(candidates: list, comp: ComplicationLevel):
        """scan DRG candidates by description keywords to match complication level."""
        keywords = {
            ComplicationLevel.MCC: ["WITH MCC", "W MCC"],
            ComplicationLevel.CC: ["WITH CC", "W CC", "WITHOUT MCC"],
            ComplicationLevel.NONE: ["WITHOUT CC/MCC", "W/O CC/MCC", "WITHOUT CC"],
        }

        targets = keywords.get(comp, [])

        # first pass — exact keyword match
        for drg in candidates:
            desc = drg.description.upper()
            for kw in targets:
                if kw in desc:
                    # avoid false match: "WITH CC" should not match "WITH MCC"
                    if comp == ComplicationLevel.CC and "WITH MCC" in desc:
                        continue
                    return drg

        # fallback — return first candidate
        return candidates[0] if candidates else None
