"""CLI entry point — run with `python -m drg` or the `drg` console script."""

from __future__ import annotations

import argparse
import json

from drg import __version__
from drg.engine import MSDRGEngine


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drg",
        description="MS-DRG grouper — assign DRG codes from ICD-10 diagnoses and procedures",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--pdx",
        required=True,
        help="principal ICD-10-CM diagnosis code (e.g. I2109)",
    )
    parser.add_argument(
        "--sdx",
        nargs="*",
        default=[],
        help="secondary ICD-10-CM diagnosis codes",
    )
    parser.add_argument(
        "--proc",
        nargs="*",
        default=[],
        help="ICD-10-PCS procedure codes",
    )
    parser.add_argument(
        "--age",
        type=int,
        default=65,
        help="patient age in years (default: 65)",
    )
    parser.add_argument(
        "--sex",
        choices=["M", "F", "U"],
        default="M",
        help="patient sex (default: M)",
    )
    parser.add_argument(
        "--discharge-status",
        default="01",
        help="discharge status code (default: 01)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="output full result as JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """run the CLI grouper."""
    args = _build_parser().parse_args(argv)

    engine = MSDRGEngine()
    result = engine.group(
        principal_dx=args.pdx,
        secondary_dxs=args.sdx,
        procedures=args.proc,
        age=args.age,
        sex=args.sex,
        discharge_status=args.discharge_status,
    )

    if args.as_json:
        print(json.dumps(result.model_dump(), indent=2, default=str))
        return

    # compact human-readable output
    print(f"DRG      : {result.drg_code}")
    print(f"desc     : {result.description}")
    print(f"MDC      : {result.mdc} — {result.mdc_description}")
    print(f"partition: {result.partition.value}")
    print(f"CC/MCC   : {result.complication_level.value}")
    print(f"weight   : {result.weight}")
    if result.geometric_los is not None:
        print(f"geo LOS  : {result.geometric_los}")
    if result.arithmetic_los is not None:
        print(f"arith LOS: {result.arithmetic_los}")


if __name__ == "__main__":
    main()
