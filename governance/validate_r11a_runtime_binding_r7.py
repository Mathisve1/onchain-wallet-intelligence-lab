#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# The approved workflow invokes this file without ``-B``.  Set the interpreter
# flag before importing any project module so provenance validation never has
# to hide or heuristically delete import-created bytecode.
sys.dont_write_bytecode = True

try:
    from governance import _validate_r11a_runtime_binding_core_r7 as _core
    from governance.r11a_repository_provenance import (
        RepositoryProvenanceError,
        authenticate_repository,
        harden_authenticated_worktree_for_bytecode_free_dispatch,
    )
    from governance.r11a_stage_common_r4 import (
        ACTIVATION_RELATIVE,
        BINDING_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        REVIEW_GATE_IDS,
        ROOT,
        require_gate_review,
        sha256 as stage_sha256,
    )
except ModuleNotFoundError:
    import _validate_r11a_runtime_binding_core_r7 as _core
    from r11a_repository_provenance import (
        RepositoryProvenanceError,
        authenticate_repository,
        harden_authenticated_worktree_for_bytecode_free_dispatch,
    )
    from r11a_stage_common_r4 import (
        ACTIVATION_RELATIVE,
        BINDING_RELATIVE,
        REVIEW_EVIDENCE_PATHS,
        REVIEW_GATE_IDS,
        ROOT,
        require_gate_review,
        sha256 as stage_sha256,
    )

_EXTRA_TRANSITIVE_PATHS = (
    "governance/_validate_r11a_runtime_binding_core_r7.py",
    "governance/r11a_github_review_evidence.py",
    "governance/r11a_repository_provenance.py",
    "governance/r11a_workflow_identity.py",
    "governance/validate_r11a_role_configuration_candidate_r4.py",
    "research/archive_inventory/r11a_corrective/_artifact_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_core_r7.py",
    "research/archive_inventory/r11a_corrective/_artifact_schema_core_r7.py",
    "research/archive_inventory/r11a_corrective/_runner_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_contract_core_r7.py",
    "research/archive_inventory/r11a_corrective/_taxonomy_core_r7.py",
    "research/archive_inventory/r11a_corrective/taxonomy_precedence_r7.py",
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
sha256 = _core.sha256


def validate(
    expected_commit: str,
    run_attempt: int,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Validate exact dispatch provenance, binding semantics, and its review.

    The runtime-binding review evidence is necessarily committed after the
    reviewed binding subject.  Repository provenance authenticates the exact
    dispatch HEAD/tree/index/worktree without requiring a parent object; the
    evidence validator independently authenticates the reviewed subject bytes
    and then consumes a review identity distinct from every earlier gate.
    """

    expected = _core.require_commit(expected_commit, "expected commit")
    _core.require(
        isinstance(run_attempt, int) and not isinstance(run_attempt, bool),
        "run attempt must be integer",
    )
    _core.require(run_attempt == 1, "runtime binding requires workflow run attempt one")
    repository_root = Path(root)
    try:
        snapshot = authenticate_repository(repository_root, expected_head=expected)
    except RepositoryProvenanceError as exc:
        raise RuntimeBindingError(f"runtime repository provenance invalid: {exc}") from exc

    lineage: list[object] = []
    binding = _core.validate_binding(root=repository_root, _review_lineage=lineage)
    evidence_relative = REVIEW_EVIDENCE_PATHS[_core.RUNTIME_BINDING_REVIEW_GATE]
    try:
        evidence_sha = stage_sha256(repository_root, evidence_relative)
        require_gate_review(
            repository_root,
            {"runtime_binding_review_evidence_sha256": evidence_sha},
            "runtime_binding_review_evidence_sha256",
            _core.RUNTIME_BINDING_REVIEW_GATE,
            target_files={
                BINDING_RELATIVE: stage_sha256(repository_root, BINDING_RELATIVE),
            },
            predecessor_files={
                ACTIVATION_RELATIVE: stage_sha256(repository_root, ACTIVATION_RELATIVE),
            },
            lineage=lineage,
        )
    except AssertionError as exc:
        raise RuntimeBindingError(str(exc)) from exc
    _core.require(
        tuple(getattr(identity, "gate_id", None) for identity in lineage)
        == REVIEW_GATE_IDS,
        "runtime binding did not consume the complete review-gate lineage",
    )
    # Keep the authenticated object live through all semantic reads and make
    # the current dispatch tree an explicit part of this function's result
    # path, even though no self-declared tree field is accepted from binding.
    _core.require(snapshot.head == expected and len(snapshot.tree) == 40, "authenticated dispatch identity drift")
    return binding


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate exact post-approval R11A R7 reviewed runtime binding"
    )
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--run-attempt", required=True, type=int)
    arguments = parser.parse_args(argv)
    validate(arguments.expected_commit, arguments.run_attempt)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        try:
            authenticated = authenticate_repository(
                ROOT,
                expected_head=arguments.expected_commit,
            )
            harden_authenticated_worktree_for_bytecode_free_dispatch(authenticated)
        except RepositoryProvenanceError as exc:
            raise RuntimeBindingError(
                f"runtime worktree bytecode boundary invalid: {exc}"
            ) from exc
    print("R11A_R7_RUNTIME_BINDING_VALID_SINGLE_USE_REVIEWED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
