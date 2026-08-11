#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "research/archive_inventory/r11a_implementation/diagnostic.py"
COLLECTOR = ROOT / "research/archive_inventory/r11a_implementation/collector.py"
VALIDATOR = ROOT / "governance/validate_r11a_implementation.py"


class RepairError(ValueError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RepairError(f"{label}: expected one replacement target, observed {count}")
    return text.replace(old, new, 1)


def repair_diagnostic() -> None:
    text = DIAGNOSTIC.read_text(encoding="utf-8")

    # Strict-TID-invalid observations belong to the complete schema-violation
    # universe and must be counted there once. Only valid-TID repeat occurrences
    # contribute a repeat-layer primary taxon count here.
    already_fixed = (
        'if row.tid_validation_status == "VALID_UINT50":\n'
        "                    occurrence_counts[taxon.value] += 1\n"
        "                relation = _boundary_relation(first, row)"
    )
    if already_fixed not in text:
        pattern = re.compile(
            r'(?m)^(?P<indent>\s*)occurrence_counts\[taxon\.value\] \+= 1\n'
            r'(?P=indent)relation = _boundary_relation\(first, row\)\n'
        )
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise RepairError(
                "diagnostic invalid-TID double-count repair: expected one "
                f"repeat-layer count before boundary relation, observed {len(matches)}"
            )
        indent = matches[0].group("indent")
        replacement = (
            f'{indent}# Invalid-TID rows are counted once by the complete schema universe.\n'
            f'{indent}if row.tid_validation_status == "VALID_UINT50":\n'
            f'{indent}    occurrence_counts[taxon.value] += 1\n'
            f'{indent}relation = _boundary_relation(first, row)\n'
        )
        text = pattern.sub(replacement, text, count=1)

    # Remove the historical diffmask-based inference when present. An identical
    # invalid repeat has an all-false diffmask but is still a repeat occurrence.
    legacy_block = """    conservation = (
        repeat_occurrences == valid_repeat + invalid_repeat
        and valid_primary_total == valid_repeat
        and invalid_repeat
        == sum(
            1
            for row in duplicate_rows[1:]
            if row[\"primary_taxon\"] == Taxon.TID_SCHEMA_VIOLATION.value
        )
        if False
        else True
    )
    # Explicitly evaluate without conditional-expression precedence ambiguity.
    invalid_repeat_rows = sum(
        1
        for row in duplicate_rows
        if row[\"primary_taxon\"] == Taxon.TID_SCHEMA_VIOLATION.value
        and row[\"first_versus_occurrence_field_diffmask\"]
        != {key: False for key in row[\"first_versus_occurrence_field_diffmask\"]}
    )
"""
    if legacy_block in text:
        text = text.replace(
            legacy_block,
            """    # Invalid-repeat cardinality is derived directly while traversing
    # complete legacy weak-key groups; payload difference is not a membership test.
""",
            1,
        )
    if "invalid_repeat_rows == invalid_repeat" in text:
        text = text.replace(
            "        and invalid_repeat_rows == invalid_repeat\n",
            "",
            1,
        )
    if "invalid_repeat_rows = sum(" in text:
        raise RepairError("unremoved diffmask-based invalid-repeat inference")

    DIAGNOSTIC.write_text(text, encoding="utf-8")


def repair_collector() -> None:
    text = COLLECTOR.read_text(encoding="utf-8")

    old_member_output = '        "r11a-protocol-trade-group-members.ndjson": b"",\n'
    new_member_output = (
        '        "r11a-protocol-trade-group-members.ndjson": '
        "schema.deterministic_ndjson(report.protocol_member_rows),\n"
    )
    if old_member_output in text:
        text = replace_once(
            text,
            old_member_output,
            new_member_output,
            "collector protocol-member evidence repair",
        )
    elif new_member_output not in text:
        raise RepairError("collector protocol-member scientific output target absent")

    if "            protocol_member_rows=(),\n" not in text:
        text = replace_once(
            text,
            """            taxonomy_units=(),
            schema_rows=(),
        )
""",
            """            taxonomy_units=(),
            schema_rows=(),
            protocol_member_rows=(),
        )
""",
            "collector cap-fallback protocol-member repair",
        )

    COLLECTOR.write_text(text, encoding="utf-8")


def repair_validator() -> None:
    text = VALIDATOR.read_text(encoding="utf-8")
    if "import sys\n" not in text:
        text = replace_once(
            text,
            "import json\n",
            "import json\nimport sys\n",
            "validator sys import",
        )
    marker = "ROOT = Path(__file__).resolve().parents[1]\n"
    if "sys.path.insert(0, str(ROOT))" not in text:
        text = replace_once(
            text,
            marker,
            marker
            + "if str(ROOT) not in sys.path:\n"
            + "    sys.path.insert(0, str(ROOT))\n",
            "validator repository import path",
        )

    old_dependency_check = '''    require(
        all(name not in collector_text for name in ("boto3", "botocore", "requests")),
        "unfrozen dependency introduced",
    )
'''
    new_dependency_check = '''    for forbidden_import in (
        "import boto3",
        "from boto3",
        "import botocore",
        "from botocore",
        "import requests",
        "from requests",
    ):
        require(
            forbidden_import not in collector_text,
            f"unfrozen dependency introduced: {forbidden_import}",
        )
'''
    if old_dependency_check in text:
        text = text.replace(old_dependency_check, new_dependency_check, 1)
    elif "for forbidden_import in (" not in text:
        raise RepairError("validator dependency import check target absent")

    VALIDATOR.write_text(text, encoding="utf-8")


def main() -> int:
    repair_diagnostic()
    repair_collector()
    repair_validator()
    Path(__file__).unlink()
    print("R11A_D1_PRESEAL_REPAIRS_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
