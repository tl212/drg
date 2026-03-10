"""code registry for ICD-10 and DRG reference data lookups."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DRGReference:
    """DRG reference record from CMS weights file."""
    drg_code: str
    description: str
    mdc: str
    drg_type: str       # SURG or MED
    weight: float
    geometric_los: Optional[float] = None
    arithmetic_los: Optional[float] = None


class CodeRegistry:
    """loads and queries ICD-10-CM, ICD-10-PCS, and DRG reference data."""

    def __init__(self) -> None:
        self._diagnoses: dict[str, str] = {}       # code -> description
        self._procedures: dict[str, str] = {}      # code -> description
        self._drg_table: dict[str, DRGReference] = {}  # drg_code -> DRGReference
        self._ready = False

    @staticmethod
    def _data_dir() -> Path:
        """path to bundled data directory."""
        return Path(__file__).parent / "data"

    # ------------------------------------------------------------------
    # loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        """load all reference data from bundled files."""
        if self._ready:
            return

        base = self._data_dir()

        # ICD-10-CM diagnoses (no header, code,description)
        cm_path = base / "cms" / "icd_10_cm.csv"
        if cm_path.exists():
            self._ingest_csv(cm_path, self._diagnoses)

        # ICD-10-PCS procedures (no header, code,description)
        pcs_path = base / "tuva" / "icd_10_pcs.csv"
        if pcs_path.exists():
            self._ingest_csv(pcs_path, self._procedures)

        # DRG weights (tab-delimited, header on line 3)
        wt_path = base / "cms" / "drg_weights.txt"
        if wt_path.exists():
            self._ingest_drg_weights(wt_path)

        self._ready = True

    def _ingest_csv(self, path: Path, target: dict[str, str]) -> None:
        """read a two-column CSV (code, description) into a dict."""
        with open(path, "r", encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if len(row) >= 2:
                    code = row[0].strip().strip('"').upper()
                    desc = row[1].strip().strip('"')
                    if code:
                        target[code] = desc

    def _ingest_drg_weights(self, path: Path) -> None:
        """parse CMS FY2026 DRG weights file (tab-delimited, cp1252)."""
        with open(path, "r", encoding="cp1252") as fh:
            lines = fh.readlines()

        # first 2 lines are title, line 3 is the header
        for raw in lines[3:]:
            raw = raw.strip()
            if not raw:
                continue

            cols = raw.split("\t")
            if len(cols) < 10:
                continue

            try:
                drg_code = cols[0].strip()
                mdc = cols[3].strip()
                drg_type = cols[4].strip()
                desc = cols[5].strip().strip('"')
                wt = float(cols[7].strip()) if cols[7].strip() else 0.0
                geo = float(cols[8].strip()) if cols[8].strip() else None
                arith = float(cols[9].strip()) if cols[9].strip() else None

                self._drg_table[drg_code] = DRGReference(
                    drg_code=drg_code,
                    description=desc,
                    mdc=mdc,
                    drg_type=drg_type,
                    weight=wt,
                    geometric_los=geo,
                    arithmetic_los=arith,
                )
            except (ValueError, IndexError):
                continue

    # ------------------------------------------------------------------
    # lookups
    # ------------------------------------------------------------------

    def lookup_diagnosis(self, code: str) -> Optional[str]:
        """return description for an ICD-10-CM code, or None."""
        return self._diagnoses.get(code.replace(".", "").upper().strip())

    def lookup_procedure(self, code: str) -> Optional[str]:
        """return description for an ICD-10-PCS code, or None."""
        return self._procedures.get(code.replace(".", "").upper().strip())

    def lookup_drg(self, drg_code: str) -> Optional[DRGReference]:
        """return DRG reference record by code (zero-padded to 3 digits)."""
        return self._drg_table.get(drg_code.strip().zfill(3))

    def find_drgs_for_mdc(
        self,
        mdc: str,
        drg_type: Optional[str] = None,
    ) -> list[DRGReference]:
        """return all DRGs that belong to a given MDC (optionally filtered by type)."""
        hits: list[DRGReference] = []
        for ref in self._drg_table.values():
            if ref.mdc == mdc:
                if drg_type is None or ref.drg_type == drg_type:
                    hits.append(ref)
        return hits

    def is_or_procedure(self, pcs_code: str) -> bool:
        """determine whether an ICD-10-PCS code is an operating-room procedure.

        uses the 7-character PCS structure:
        pos 0 = section, pos 2 = root operation, pos 4 = approach.
        """
        code = pcs_code.upper().strip()
        if len(code) != 7:
            return False

        section = code[0]
        root_op = code[2]
        approach = code[4]

        if section == "0":
            # root operations that almost always require OR
            major_ops = {"1", "6", "G", "M", "R", "S", "T", "Y"}
            if root_op in major_ops:
                return True

            # broad set of root operations that may require OR
            or_ops = {
                "2", "4", "5", "7", "8", "9", "B", "C", "D", "F",
                "H", "J", "K", "L", "N", "P", "Q", "U", "V", "W", "X",
            }

            # open approach
            if approach == "0":
                return root_op in or_ops
            # percutaneous endoscopic
            if approach == "4":
                return root_op in or_ops
            # percutaneous — cardiac cath lab counts as surgical for DRG
            if approach == "3":
                body_system = code[1]
                if body_system == "2":
                    return True
                return root_op in major_ops

        # section 5 = extracorporeal assistance (ECMO, etc.)
        if section == "5":
            return True

        # section X = new technology
        if section == "X":
            return True

        return False

    # ------------------------------------------------------------------
    # stats
    # ------------------------------------------------------------------

    def diagnosis_count(self) -> int:
        """number of loaded ICD-10-CM codes."""
        return len(self._diagnoses)

    def drg_count(self) -> int:
        """number of loaded DRG records."""
        return len(self._drg_table)
