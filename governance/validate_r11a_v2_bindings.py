#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BINDING = ROOT / "research/archive_inventory/r11a_v2/R11A_V2_PREREGISTRATION_BINDINGS.json"


class BindingValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BindingValidationError(message)


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        require(key not in result, f"duplicate JSON key in V2 bindings: {key}")
        result[key] = value
    return result


def _constant(token: str) -> Any:
    raise BindingValidationError(f"non-finite V2 binding value: {token}")


def main() -> int:
    if not BINDING.is_file():
        raise BindingValidationError("R11A V2 preregistration binding file absent")
    from governance import seal_r11a_v2_preregistration as seal

    expected = seal.expected()
    try:
        observed = json.loads(
            BINDING.read_text(encoding="utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BindingValidationError(f"binding file parse failed: {exc}") from exc
    require(observed == expected, "R11A V2 preregistration bindings drift")
    require(observed["status"] == "SEALED_PREREGISTRATION_NO_EXECUTION", "binding status drift")
    require(observed["owner_approval_eligible"] is False, "binding opens owner approval")
    require(observed["network_execution_authorized"] is False, "binding opens network execution")
    require(observed["r11_closed"] is False and observed["r12_ready"] is False, "binding overclaims lifecycle")
    require(observed["empirical_result"] is None, "binding contains empirical result")
    print("R11A_V2_PREREGISTRATION_BINDINGS_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
