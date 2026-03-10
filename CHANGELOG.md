# Changelog

## v1.0.0

Initial release.

- MS-DRG grouping engine (`MSDRGEngine`) with `group()` API
- CMS FY2026 v43.0 data (ICD-10-CM, CC/MCC lists, CC exclusions, DRG weights)
- Tuva Health reference data (ICD-10-PCS, MDC, MS-DRG)
- CC/MCC complication resolution with PDX exclusion support
- MDC classification from principal diagnosis (ICD-10-CM range mapping)
- Pre-MDC assignment (transplants, ECMO, tracheostomy, bone marrow, CAR-T)
- Surgical/medical partition via OR procedure detection
- Diagnosis-specific DRG families for MDC 04 (respiratory) and MDC 05 (circulatory)
- Procedure-specific DRG families for cardiac procedures
- CLI entry point (`python -m drg`) with human-readable and JSON output
- Pydantic models for typed input/output (`Encounter`, `Diagnosis`, `Procedure`, `GroupingResult`)
- 81 tests
