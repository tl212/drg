"""major diagnostic category classification from principal diagnosis."""

import csv
from pathlib import Path
from typing import Optional  # noqa: UP035

# CMS ICD-10-CM code range → MDC mapping (public domain, CMS definitions manual).
# format: (range_start, range_end, mdc)
# more specific ranges appear later to override broader ones.
_PDX_MDC_MAP: list[tuple[str, str, str]] = [
    # mdc 01 — nervous system
    ("A17", "A179", "01"),
    ("A321", "A321", "01"),
    ("A390", "A394", "01"),
    ("A50", "A509", "01"),
    ("A521", "A521", "01"),
    ("A80", "A89", "01"),
    ("B00", "B004", "01"),
    ("B01", "B011", "01"),
    ("B02", "B021", "01"),
    ("B26", "B262", "01"),
    ("B37", "B375", "01"),
    ("B38", "B384", "01"),
    ("B45", "B451", "01"),
    ("G00", "G99", "01"),
    ("F01", "F09", "01"),
    ("R40", "R4082", "01"),
    ("R41", "R419", "01"),
    ("R47", "R479", "01"),
    ("R55", "R55", "01"),
    ("R56", "R569", "01"),

    # mdc 02 — eye
    ("H00", "H59", "02"),
    ("B30", "B309", "02"),

    # mdc 03 — ear, nose, mouth, throat
    ("H60", "H95", "03"),
    ("J00", "J06", "03"),
    ("J30", "J39", "03"),
    ("K00", "K14", "03"),

    # mdc 04 — respiratory system
    ("J09", "J18", "04"),
    ("J20", "J22", "04"),
    ("J40", "J47", "04"),
    ("J60", "J70", "04"),
    ("J80", "J84", "04"),
    ("J85", "J86", "04"),
    ("J90", "J94", "04"),
    ("J95", "J95", "04"),
    ("J96", "J99", "04"),
    ("R04", "R049", "04"),
    ("R05", "R059", "04"),
    ("R06", "R069", "04"),
    ("R09", "R099", "04"),

    # mdc 05 — circulatory system
    ("I00", "I99", "05"),
    ("R00", "R03", "05"),
    ("R07", "R079", "05"),
    ("R57", "R579", "05"),
    ("R58", "R58", "05"),

    # mdc 06 — digestive system
    ("K20", "K95", "06"),
    ("R10", "R19", "06"),

    # mdc 07 — hepatobiliary system and pancreas
    ("K70", "K77", "07"),
    ("K80", "K87", "07"),
    ("B15", "B19", "07"),

    # mdc 08 — musculoskeletal system and connective tissue
    ("M00", "M99", "08"),
    ("S00", "S99", "08"),
    ("T20", "T32", "08"),

    # mdc 09 — skin, subcutaneous tissue, breast
    ("L00", "L99", "09"),
    ("N60", "N65", "09"),

    # mdc 10 — endocrine, nutritional, metabolic
    ("E00", "E89", "10"),
    ("R63", "R639", "10"),
    ("R73", "R739", "10"),

    # mdc 11 — kidney and urinary tract
    ("N00", "N39", "11"),
    ("R30", "R39", "11"),

    # mdc 12 — male reproductive system
    ("N40", "N53", "12"),

    # mdc 13 — female reproductive system
    ("N70", "N98", "13"),

    # mdc 14 — pregnancy, childbirth, puerperium
    ("O00", "O9A", "14"),

    # mdc 15 — newborns and neonates
    ("P00", "P96", "15"),

    # mdc 16 — blood, blood-forming organs, immunological
    ("D50", "D89", "16"),

    # mdc 17 — myeloproliferative diseases
    ("C81", "C96", "17"),
    ("D45", "D479", "17"),

    # mdc 18 — infectious and parasitic diseases
    ("A00", "B99", "18"),
    ("R50", "R509", "18"),
    ("R65", "R659", "18"),

    # mdc 19 — mental diseases and disorders
    ("F10", "F99", "19"),

    # mdc 20 — substance use disorders
    ("F10", "F19", "20"),
    ("T40", "T409", "20"),
    ("T51", "T519", "20"),

    # mdc 21 — injuries, poisonings, toxic effects
    ("S00", "T88", "21"),

    # mdc 22 — burns
    ("T20", "T32", "22"),

    # mdc 23 — factors influencing health status
    ("Z00", "Z99", "23"),

    # --- specific overrides (must come after broad ranges) ---

    # mdc 25 — HIV (overrides A00-B99 and Z00-Z99)
    ("B20", "B20", "25"),
    ("Z21", "Z21", "25"),

    # mdc 14 — pregnancy Z-codes (overrides Z00-Z99)
    ("Z33", "Z339", "14"),
    ("Z34", "Z349", "14"),
    ("Z3A", "Z3A49", "14"),

    # mdc 15 — newborn Z-codes (overrides Z00-Z99)
    ("Z38", "Z389", "15"),
]


class MDCClassifier:
    """classifies principal diagnosis into a major diagnostic category.

    uses CMS-defined ICD-10-CM code ranges to determine MDC.
    more specific ranges override broader ones (last-match wins).
    MDC 24 (multiple significant trauma) is handled externally by
    the engine based on multi-trauma criteria.
    """

    def __init__(self) -> None:
        self._mdc_descriptions: dict[str, str] = {}
        self._ready = False

    @staticmethod
    def _data_dir() -> Path:
        return Path(__file__).parent / "data"

    # ------------------------------------------------------------------
    # loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        """load MDC reference descriptions from tuva data."""
        if self._ready:
            return

        mdc_path = self._data_dir() / "tuva" / "mdc.csv"
        if mdc_path.exists():
            self._ingest_mdc_descriptions(mdc_path)

        self._ready = True

    def _ingest_mdc_descriptions(self, path: Path) -> None:
        """parse tuva mdc.csv into a code -> description mapping."""
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if len(row) >= 2:
                    code = row[0].strip().strip('"')
                    desc = row[1].strip().strip('"')
                    if code:
                        self._mdc_descriptions[code] = desc

    # ------------------------------------------------------------------
    # classification
    # ------------------------------------------------------------------

    def classify(self, principal_dx: str) -> tuple[str, str]:
        """determine MDC for a principal diagnosis code.

        args:
            principal_dx: ICD-10-CM code (with or without dots)

        returns:
            (mdc_code, mdc_description) — ("00", "unassigned") when
            no range matches.
        """
        norm = principal_dx.replace(".", "").upper().strip()
        if not norm:
            return "00", "unassigned"

        mdc = self._match_range(norm)
        if mdc:
            return mdc, self._mdc_descriptions.get(mdc, "")

        return "00", "unassigned"

    @staticmethod
    def _match_range(code: str) -> Optional[str]:
        """find the last matching MDC range for *code* (last-match wins)."""
        hit: Optional[str] = None

        for lo, hi, mdc in _PDX_MDC_MAP:
            if _in_range(code, lo, hi):
                hit = mdc

        return hit

    def description(self, mdc_code: str) -> str:
        """return the description for an MDC code."""
        return self._mdc_descriptions.get(mdc_code, "")


# ------------------------------------------------------------------
# range comparison helper
# ------------------------------------------------------------------

def _in_range(code: str, lo: str, hi: str) -> bool:
    """check whether *code* falls within [lo, hi] lexicographically.

    shorter codes are padded so sub-codes are included:
    - lo is padded with '0' (inclusive lower bound)
    - hi is padded with '9' (inclusive upper bound)
    """
    code = code.upper()
    lo = lo.upper()
    hi = hi.upper()

    # truncate code to comparison length if longer than the range end
    prefix = code[: len(hi)] if len(code) > len(hi) else code

    padded = prefix.ljust(len(hi), "0")
    lo_padded = lo.ljust(len(hi), "0")
    hi_padded = hi.ljust(len(hi), "9")

    return lo_padded <= padded <= hi_padded
