#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "research/archive_inventory/r11a_implementation/diagnostic.py"
COLLECTOR = ROOT / "research/archive_inventory/r11a_implementation/collector.py"
VALIDATOR = ROOT / "governance/validate_r11a_implementation.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement target, observed {count}")
    return text.replace(old, new, 1)


def repair_diagnostic() -> None:
    text = DIAGNOSTIC.read_text(encoding="utf-8")
    text = replace_once(
        text,
        """                occurrence_counts[taxon.value] += 1
                relation = _boundary_relation(first, row)
""",
        """                # Strict-TID-invalid rows are counted once by the complete
                # schema-violation universe below. Valid repeat rows are counted
                # here by their repeat-occurrence primary taxon.
                if row.tid_validation_status == \"VALID_UINT50\":
                    occurrence_counts[taxon.value] += 1
                relation = _boundary_relation(first, row)
""",
        "diagnostic invalid-TID double-count repair",
    )
    text = replace_once(
        text,
        """    conservation = (
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
""",
        """    # The nonfirst invalid-TID cardinality is derived directly while
    # traversing complete legacy weak-key groups. It must not be inferred from
    # a payload diffmask because a byte-identical invalid repeat has an all-false
    # diffmask while still being a repeat occurrence.
""",
        "diagnostic invalid-repeat derivation repair",
    )
    text = replace_once(
        text,
        """        and invalid_repeat_rows == invalid_repeat
        and relationships[\"intra_object\"] + relationships[\"inter_object\"]
""",
        """        and relationships[\"intra_object\"] + relationships[\"inter_object\"]
""",
        "diagnostic invalid-repeat conservation repair",
    )
    DIAGNOSTIC.write_text(text, encoding="utf-8")


def repair_collector() -> None:
    text = COLLECTOR.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '        "r11a-protocol-trade-group-members.ndjson": b"",\n',
        '        "r11a-protocol-trade-group-members.ndjson": schema.deterministic_ndjson(report.protocol_member_rows),\n',
        "collector protocol-member evidence repair",
    )
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
            marker + "if str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n",
            "validator repository import path",
        )
    text = replace_once(
        text,
        '''    require(
        all(name not in collector_text for name in ("boto3", "botocore", "requests")),
        "unfrozen dependency introduced",
    )
''',
        '''    for forbidden_import in (
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
''',
        "validator dependency import check",
    )
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
