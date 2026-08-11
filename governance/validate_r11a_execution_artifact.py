#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.archive_inventory.r11a_corrective.artifact_r3 import (  # noqa: E402
    CONTEXT_FILE,
    RESULT_FILE,
    validate_artifact,
)
from research.archive_inventory.r11a_corrective.canonical import (  # noqa: E402
    FrozenObject,
    NumberToken,
    strict_json_loads,
)
from research.archive_inventory.r11a_corrective.limits import DEFAULT_LIMITS  # noqa: E402


class ValidationError(AssertionError):
    pass


def object_value(value: object, label: str) -> FrozenObject:
    if not isinstance(value, FrozenObject):
        raise ValidationError(f"{label} must be object")
    return value


def integer(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValidationError(f"{label} must be exact integer")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--expected-run-id", type=int)
    arguments = parser.parse_args()
    validate_artifact(arguments.artifact_dir, DEFAULT_LIMITS)
    result = object_value(
        strict_json_loads((arguments.artifact_dir / RESULT_FILE).read_bytes()), "result"
    )
    context = object_value(
        strict_json_loads((arguments.artifact_dir / CONTEXT_FILE).read_bytes()), "context"
    )
    if arguments.expected_run_id is not None:
        if integer(context["workflow_run_id"], "workflow_run_id") != arguments.expected_run_id:
            raise ValidationError("artifact run ID differs from current GitHub run")
    if context.get("workflow_run_attempt") is not None:
        if integer(context["workflow_run_attempt"], "workflow_run_attempt") != 1:
            raise ValidationError("artifact was produced by a rerun")
    terminal = result["terminal_class"]
    allowed = {
        "R11A_ROOT_CAUSE_TAXONOMY_COMPLETE": 0,
        "R11A_DIAGNOSTIC_INCOMPLETE": 20,
        "R11A_ARTIFACT_CAP_EXCEEDED": 21,
    }
    if terminal not in allowed:
        raise ValidationError("artifact terminal class is not preregistered")
    if integer(result["return_code"], "return_code") != allowed[terminal]:
        raise ValidationError("artifact return code and terminal class differ")
    if result["wallet_ranking_performed"] is not False:
        raise ValidationError("artifact opens wallet ranking")
    if result["pnl_or_alpha_analysis_performed"] is not False:
        raise ValidationError("artifact opens PnL or alpha analysis")
    if result["copyability_analysis_performed"] is not False:
        raise ValidationError("artifact opens copyability analysis")
    if result["trading_authority_opened"] is not False:
        raise ValidationError("artifact opens trading authority")
    print("R11A_EXECUTION_ARTIFACT_VALID_BEFORE_UPLOAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
