#!/usr/bin/env python3
from __future__ import annotations

from governance import _validate_r11a_runtime_binding_core_r7 as _core

_EXTRA_TRANSITIVE_PATHS = (
    "governance/_validate_r11a_runtime_binding_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_schema_core_r7.py",
    "research/archive_inventory/r11a_corrective/_runner_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_core_r7.py",
)

_core.TRANSITIVE_CODE_PATHS = tuple(
    sorted(
        set((*_core.TRANSITIVE_CODE_PATHS, *_EXTRA_TRANSITIVE_PATHS)),
        key=lambda value: value.encode("utf-8"),
    )
)
_core.REQUIRED_BOUND_PATHS = tuple(
    sorted(
        set((*_core.REQUIRED_BOUND_PATHS, *_EXTRA_TRANSITIVE_PATHS)),
        key=lambda value: value.encode("utf-8"),
    )
)

BINDING = _core.BINDING
BINDING_RELATIVE = _core.BINDING_RELATIVE
DIAGNOSTIC_ID = _core.DIAGNOSTIC_ID
IMPLEMENTATION_ID = _core.IMPLEMENTATION_ID
REQUIRED_BOUND_PATHS = _core.REQUIRED_BOUND_PATHS
RuntimeBindingError = _core.RuntimeBindingError
TRANSITIVE_CODE_PATHS = _core.TRANSITIVE_CODE_PATHS
load = _core.load
main = _core.main
sha256 = _core.sha256
validate = _core.validate


if __name__ == "__main__":
    raise SystemExit(main())
