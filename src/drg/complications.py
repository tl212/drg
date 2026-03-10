"""CC/MCC complication resolver with exclusion support."""

import re
from pathlib import Path

from drg.schemas import ComplicationLevel


class ComplicationResolver:
    """resolves CC/MCC complication level from secondary diagnoses.

    loads CMS CC list, MCC list, and CC exclusion tables.
    the exclusion tables define which principal diagnoses prevent a
    secondary diagnosis from counting as a CC or MCC.
    """

    def __init__(self) -> None:
        self._mcc_codes: set[str] = set()
        self._cc_codes: set[str] = set()
        # maps a CC/MCC secondary code -> set of principal dx codes that exclude it
        self._exclusions: dict[str, set[str]] = {}
        # maps a CC/MCC secondary code -> its PDX collection number
        self._code_to_collection: dict[str, str] = {}
        self._ready = False

    @staticmethod
    def _data_dir() -> Path:
        return Path(__file__).parent / "data"

    # ------------------------------------------------------------------
    # loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        """load CC, MCC, and exclusion data from CMS files."""
        if self._ready:
            return

        base = self._data_dir()

        mcc_path = base / "cms" / "mcc_list.txt"
        if mcc_path.exists():
            self._ingest_severity_list(mcc_path, self._mcc_codes)

        cc_path = base / "cms" / "cc_list.txt"
        if cc_path.exists():
            self._ingest_severity_list(cc_path, self._cc_codes)

        excl_path = base / "cms" / "cc_exclusions.txt"
        if excl_path.exists():
            self._ingest_exclusions(excl_path)

        self._ready = True

    def _ingest_severity_list(self, path: Path, target: set[str]) -> None:
        """parse a CMS CC or MCC list file (tab-delimited: code \\t description)."""
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("TABLE") or line.startswith("Diagnosis"):
                    continue
                parts = line.strip().split("\t")
                if parts and len(parts) >= 1:
                    code = parts[0].strip().replace(".", "").upper()
                    if code and len(code) >= 3:
                        target.add(code)

    def _ingest_exclusions(self, path: Path) -> None:
        """parse CMS table 6K CC exclusions file.

        the file has two sections:
        - part 1 (lines 11 .. ~18443): each CC/MCC code with its PDX collection
          reference, e.g. ' A000    CC  0002:3 codes     Cholera...'
          codes with 'No Excl' have no exclusions.
        - part 2 (line ~18445 onward): 'PDX collection NNNN' blocks listing
          principal diagnosis codes that, when used as the principal dx,
          exclude the CC/MCC from counting.
        """
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()

        # --- pass 1: build code -> collection mapping from part 1 ---
        # pattern: leading whitespace, code, CC/MCC flag, collection:count or 'No Excl'
        part1_re = re.compile(
            r"^\s+([A-Z0-9]+)\s+(?:CC|MCC)\s+(\d{4}):\d",
            re.MULTILINE,
        )
        for m in part1_re.finditer(raw):
            cc_code = m.group(1).strip().upper()
            collection_id = m.group(2)
            self._code_to_collection[cc_code] = collection_id

        # --- pass 2: parse PDX collection blocks from part 2 ---
        # each block starts with 'PDX collection NNNN' followed by indented codes
        collections: dict[str, set[str]] = {}
        current_collection: str | None = None

        for line in raw.splitlines():
            coll_match = re.match(r"^PDX collection (\d+)", line)
            if coll_match:
                current_collection = coll_match.group(1)
                collections[current_collection] = set()
                continue

            if current_collection is not None:
                stripped = line.strip()
                if not stripped:
                    # blank line ends the collection block
                    current_collection = None
                    continue
                # extract just the code (first token)
                pdx_code = stripped.split()[0].strip().upper()
                if pdx_code and len(pdx_code) >= 3:
                    collections[current_collection].add(pdx_code)

        # --- pass 3: map each CC/MCC code to its set of excluding PDX codes ---
        for cc_code, coll_id in self._code_to_collection.items():
            pdx_set = collections.get(coll_id)
            if pdx_set:
                self._exclusions[cc_code] = pdx_set

    # ------------------------------------------------------------------
    # resolution
    # ------------------------------------------------------------------

    def resolve(
        self,
        principal_dx: str,
        secondary_dxs: list[str],
        discharge_status: str,
    ) -> tuple[ComplicationLevel, list[str], list[str]]:
        """determine complication level from secondary diagnoses.

        args:
            principal_dx: principal ICD-10-CM code
            secondary_dxs: list of secondary ICD-10-CM codes
            discharge_status: discharge status code

        returns:
            (complication_level, cc_codes_applied, mcc_codes_applied)
        """
        pdx = principal_dx.replace(".", "").upper()
        cc_applied: list[str] = []
        mcc_applied: list[str] = []

        for dx in secondary_dxs:
            norm = dx.replace(".", "").upper()

            # check exclusion — skip if principal dx excludes this code
            excluded_by = self._exclusions.get(norm, set())
            if pdx in excluded_by:
                continue

            if norm in self._mcc_codes:
                mcc_applied.append(norm)
            elif norm in self._cc_codes:
                cc_applied.append(norm)

        if mcc_applied:
            return ComplicationLevel.MCC, cc_applied, mcc_applied
        if cc_applied:
            return ComplicationLevel.CC, cc_applied, mcc_applied
        return ComplicationLevel.NONE, cc_applied, mcc_applied

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------

    def is_mcc(self, code: str) -> bool:
        """check whether a code is classified as MCC."""
        return code.replace(".", "").upper() in self._mcc_codes

    def is_cc(self, code: str) -> bool:
        """check whether a code is classified as CC (but not MCC)."""
        norm = code.replace(".", "").upper()
        return norm in self._cc_codes and norm not in self._mcc_codes

    def exclusion_count(self) -> int:
        """number of CC/MCC codes with at least one PDX exclusion."""
        return len(self._exclusions)
