# drg

Python MS-DRG grouper — assigns Medicare Severity Diagnosis-Related Group codes from ICD-10 diagnoses and procedures.

Implements the CMS MS-DRG algorithm (FY2026 v43.0) as a pure Python package with zero external service dependencies.

## Installation

```bash
pip install drg
```

## Quick Start

### Python API

```python
from drg import MSDRGEngine

engine = MSDRGEngine()

result = engine.group(
    principal_dx="I2109",
    secondary_dxs=["J9601", "E1165"],
    procedures=["02703DZ"],
    age=67,
    sex="M",
)

print(result.drg_code)          # "280"
print(result.description)       # "ACUTE MYOCARDIAL INFARCTION, DISCHARGED ALIVE WITH MCC"
print(result.weight)            # 1.2345
print(result.mdc)               # "05"
print(result.complication_level) # ComplicationLevel.MCC
```

### Command Line

```bash
# human-readable output
python -m drg --pdx I2109 --sdx J9601 E1165 --proc 02703DZ --age 67 --sex M

# JSON output
python -m drg --pdx I2109 --json
```

### CLI Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--pdx` | Principal ICD-10-CM diagnosis code | **required** |
| `--sdx` | Secondary ICD-10-CM codes (space-separated) | none |
| `--proc` | ICD-10-PCS procedure codes (space-separated) | none |
| `--age` | Patient age in years | 65 |
| `--sex` | Patient sex (M/F/U) | M |
| `--discharge-status` | Discharge status code | 01 |
| `--json` | Output full result as JSON | false |
| `-V` / `--version` | Print version and exit | — |

## How It Works

The grouper follows the CMS MS-DRG classification logic:

1. **Pre-MDC check** — transplants, ECMO, tracheostomy, and CAR-T therapy (DRGs 001–019)
2. **MDC classification** — assigns a Major Diagnostic Category based on the principal diagnosis
3. **Surgical/medical partition** — determines whether the encounter is surgical (OR procedure present) or medical
4. **Complication resolution** — evaluates secondary diagnoses for CC/MCC status, applying PDX-based exclusions
5. **DRG assignment** — selects the final DRG based on MDC, partition, and complication level

## API Reference

### `MSDRGEngine`

The main entry point. Data files are lazy-loaded on first call to `group()`.

```python
engine = MSDRGEngine()
result = engine.group(
    principal_dx="I2109",       # ICD-10-CM code (dots optional)
    secondary_dxs=["E1165"],    # secondary ICD-10-CM codes
    procedures=["02703DZ"],     # ICD-10-PCS codes
    age=67,                     # patient age
    sex="M",                    # M/F/U
    discharge_status="01",      # discharge status code
)
```

### `GroupingResult`

Returned by `engine.group()`. Key fields:

- `drg_code` — MS-DRG code (e.g. `"282"`)
- `description` — DRG description
- `mdc` — Major Diagnostic Category code (e.g. `"05"`)
- `mdc_description` — MDC description
- `weight` — DRG relative weight
- `geometric_los` — geometric mean length of stay
- `arithmetic_los` — arithmetic mean length of stay
- `partition` — `PartitionType.SURGICAL` or `PartitionType.MEDICAL`
- `complication_level` — `ComplicationLevel.MCC`, `.CC`, or `.NONE`
- `is_pre_mdc` — true for DRGs 001–019
- `principal_diagnosis` — echoed `Diagnosis` object
- `secondary_diagnoses` — echoed list of `Diagnosis` objects
- `procedures` — echoed list of `Procedure` objects
- `encounter` — echoed `Encounter` object
- `has_or_procedure` — true if an OR procedure was detected
- `cc_codes_applied` — CC codes that contributed to complication level
- `mcc_codes_applied` — MCC codes that contributed to complication level

## Data Sources

This package bundles public domain and open-source reference data:

- **CMS FY2026 Final Rule** — ICD-10-CM codes, CC/MCC lists, CC exclusions, DRG weights
  Source: [cms.gov](https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/ms-drg-classifications-and-software)
  License: U.S. government public domain

- **Tuva Health** — ICD-10-PCS codes, MDC reference, MS-DRG reference
  Source: [github.com/tuva-health/the_tuva_project](https://github.com/tuva-health/the_tuva_project)
  License: Apache 2.0

## Supported Version

- **MS-DRG v43.0** (FY2026 Final Rule)
- ICD-10-CM/PCS effective October 1, 2025

## Limitations

- Diagnosis-specific DRG families are currently implemented for MDC 04 (respiratory) and MDC 05 (circulatory). Other MDCs fall back to severity-keyword matching against the DRG weights table.
- MDC 24 (multiple significant trauma) is not yet implemented — it requires multi-body-region injury criteria beyond single-PDX classification.
- The grouper covers the most common DRG assignment paths. Edge cases in less common MDCs may produce a fallback result.

## Development

```bash
git clone https://github.com/tl212/drg.git
cd drg
pip install -e ".[dev]"
pytest
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
