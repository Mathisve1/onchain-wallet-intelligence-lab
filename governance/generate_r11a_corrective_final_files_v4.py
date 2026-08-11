#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORRECTIVE = ROOT / "research/archive_inventory/r11a_corrective"
GOVERNANCE = ROOT / "governance"
TESTS = ROOT / "tests"


class GenerationError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise GenerationError(f"{label}: expected exactly one match, observed {count}")
    return text.replace(old, new, 1)


def replace_function(path: Path, function_name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    target = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ),
        None,
    )
    if target is None or target.end_lineno is None:
        raise GenerationError(f"function not found: {path}:{function_name}")
    lines = text.splitlines(keepends=True)
    lines[target.lineno - 1 : target.end_lineno] = [replacement.rstrip() + "\n\n"]
    path.write_text("".join(lines), encoding="utf-8")


def patch_integral_normalizer() -> None:
    path = CORRECTIVE / "canonical.py"
    text = path.read_text(encoding="utf-8")
    if "Normalize a mathematical integer without Decimal context or large allocation" in text:
        return
    replacement = '''def mathematically_integral_number(value: NumberToken) -> str | None:
    """Normalize a mathematical integer without Decimal context or large allocation."""
    match = _NUMBER_RE.fullmatch(value.token)
    if match is None:
        return None
    sign, integer_part, fractional_part, exponent_text = match.groups()
    fractional = fractional_part or ""
    exponent = int(exponent_text or "0", 10)
    coefficient = integer_part + fractional
    decimal_shift = exponent - len(fractional)
    maximum_digits = 4096
    if decimal_shift >= 0:
        if len(coefficient) + decimal_shift > maximum_digits:
            raise CanonicalJSONError("integral decimal token exceeds normalized length cap")
        digits = coefficient + "0" * decimal_shift
    else:
        cut = len(coefficient) + decimal_shift
        if cut <= 0:
            if any(character != "0" for character in coefficient):
                return None
            digits = "0"
        else:
            if any(character != "0" for character in coefficient[cut:]):
                return None
            digits = coefficient[:cut]
    digits = digits.lstrip("0") or "0"
    if len(digits) > maximum_digits:
        raise CanonicalJSONError("integral decimal token exceeds normalized length cap")
    if sign == "-" and digits != "0":
        return "-" + digits
    return digits
'''
    replace_function(path, "mathematically_integral_number", replacement)


def patch_lz4_line_cap() -> None:
    path = CORRECTIVE / "lz4stream.py"
    text = path.read_text(encoding="utf-8")
    if "_MAX_RECORD_BYTES" not in text:
        text = replace_once(
            text,
            "_MASK: Final[int] = 0xFFFFFFFF\n",
            "_MASK: Final[int] = 0xFFFFFFFF\n_MAX_RECORD_BYTES: Final[int] = 16 << 20\n",
            "LZ4 record cap constant",
        )
        text = replace_once(
            text,
            '''                    self._record_count += 1
                    yield line
            if line_buffer:
''',
            '''                    self._record_count += 1
                    yield line
                if len(line_buffer) > _MAX_RECORD_BYTES:
                    raise LZ4StreamError("one decompressed archive record exceeds bounded line buffer")
            if line_buffer:
''',
            "LZ4 bounded partial-record buffer",
        )
        path.write_text(text, encoding="utf-8")


def patch_protocol_singletons() -> None:
    path = CORRECTIVE / "taxonomy_r4.py"
    text = path.read_text(encoding="utf-8")
    marker = "if occurrences <= 1:\n                continue\n            expected = not overflow"
    if marker not in text:
        text = replace_once(
            text,
            "            expected = not overflow and bool(blocks) and all(state.is_expected_pair() for state in blocks.values())\n",
            "            if occurrences <= 1:\n                continue\n            expected = not overflow and bool(blocks) and all(state.is_expected_pair() for state in blocks.values())\n",
            "protocol singleton exclusion",
        )
        path.write_text(text, encoding="utf-8")


def patch_join_cleanup() -> None:
    path = CORRECTIVE / "join.py"
    text = path.read_text(encoding="utf-8")
    marker = "if directory.exists():\n            directory.rmdir()\n        return tuple(sorted_paths)"
    if marker not in text:
        text = replace_once(
            text,
            "        return tuple(sorted_paths), tuple(rows)\n",
            "        if directory.exists():\n            directory.rmdir()\n        return tuple(sorted_paths), tuple(rows)\n",
            "disk join source-directory cleanup",
        )
        path.write_text(text, encoding="utf-8")


def patch_boundary_validation() -> None:
    path = CORRECTIVE / "artifact_r3.py"
    text = path.read_text(encoding="utf-8")
    if "package boundary file-count formula mismatch" in text:
        return
    replacement = '''def validate_boundary(path: Path, limits: R11ALimits) -> None:
    raw = path.read_bytes()
    if len(raw) != limits.package_boundary_bytes or not raw.endswith(b"\\n"):
        raise ArtifactError("package boundary size or newline mismatch")
    value = _object(strict_json_loads(raw.rstrip(b" \\n") + b"\\n"), "package boundary")
    for key in (
        "metadata_within_reservation",
        "final_staging_within_artifact_limit",
        "preupload_runtime_within_hard_limit_after_upload_window",
        "boundary_write_within_workspace_limit",
    ):
        if _integer(value[key], key) != 1:
            raise ArtifactError(f"package boundary flag is not one: {key}")
    if _integer(value["maximum_retained_artifact_bytes"], "artifact cap") != limits.maximum_retained_artifact_bytes:
        raise ArtifactError("package boundary artifact cap drift")
    if _integer(value["maximum_ephemeral_workspace_bytes"], "workspace cap") != limits.maximum_ephemeral_workspace_bytes:
        raise ArtifactError("package boundary workspace cap drift")
    preboundary_files = tuple(
        candidate
        for candidate in path.parent.iterdir()
        if candidate.is_file() and candidate.name != BOUNDARY_FILE
    )
    actual_preboundary_bytes = sum(candidate.stat().st_size for candidate in preboundary_files)
    actual_metadata_bytes = sum(
        candidate.stat().st_size
        for candidate in preboundary_files
        if candidate.name not in SCIENCE_CONTAINERS
    )
    if _integer(value["preboundary_file_count"], "preboundary file count") != len(preboundary_files):
        raise ArtifactError("package boundary file-count formula mismatch")
    if _integer(value["preboundary_bytes"], "preboundary bytes") != actual_preboundary_bytes:
        raise ArtifactError("package boundary preboundary-byte formula mismatch")
    if _integer(value["total_bytes_before_boundary"], "total bytes before boundary") != actual_preboundary_bytes:
        raise ArtifactError("package boundary total-byte formula mismatch")
    if _integer(value["metadata_bytes"], "metadata bytes") != actual_metadata_bytes:
        raise ArtifactError("package boundary metadata-byte formula mismatch")
    if directory_size(path.parent) != actual_preboundary_bytes + limits.package_boundary_bytes:
        raise ArtifactError("package boundary final directory-size formula mismatch")
'''
    replace_function(path, "validate_boundary", replacement)


def patch_entrypoint_failure_fallback() -> None:
    path = CORRECTIVE / "entrypoint_r5.py"
    text = path.read_text(encoding="utf-8")
    if "PRECOLLECTOR_EXECUTION_SETUP_FAILURE" in text:
        return
    text = replace_once(
        text,
        "from .preflight_artifact import write_pre_oidc_failure_artifact\n",
        "from .preflight_artifact import _checked_remove, write_pre_oidc_failure_artifact\n",
        "entrypoint checked failure cleanup import",
    )
    path.write_text(text, encoding="utf-8")
    replacement = '''def execute(workspace: Path, context_path: Path, principal_path: Path) -> int:
    raw_context = context_path.read_bytes()
    try:
        workflow = WorkflowContext.from_bytes(raw_context)
        principal = PrincipalEvidence.from_bytes(principal_path.read_bytes())
        snapshot = PricingSnapshot.load()
        projected = snapshot.projected_eur_micros(
            72, DEFAULT_SELECTION.aggregate_expected_compressed_bytes
        )
        context = combined_context(
            workflow, principal, pricing_projection_eur_micros=projected
        )
        result = run_network(
            inputs=RunInputs(workspace=workspace, context=context),
            credentials=AWSCredentials.from_environment(),
            pricing_snapshot=snapshot,
        )
        print(result.artifact.final_directory)
        return result.artifact.return_code
    except Exception as exc:
        context = _minimal_context(raw_context, None, None)
        context["execution_phase"] = "PRECOLLECTOR_FAILURE_AFTER_STATIC_GATES"
        context["principal_observed"] = principal_path.exists()
        context["failure_exception_type_sha256"] = hashlib.sha256(
            type(exc).__name__.encode("utf-8")
        ).hexdigest()
        if workspace.exists():
            _checked_remove(workspace)
        outcome = write_pre_oidc_failure_artifact(
            workspace=workspace,
            context=context,
            failure_code="PRECOLLECTOR_EXECUTION_SETUP_FAILURE",
        )
        print(outcome)
        return 21
'''
    replace_function(path, "execute", replacement)


def generate_artifact_validator_r4() -> None:
    destination = GOVERNANCE / "validate_r11a_execution_artifact_r4.py"
    if destination.exists() and "canonical_json_bytes" in destination.read_text(encoding="utf-8"):
        return
    source = GOVERNANCE / "validate_r11a_execution_artifact_r3.py"
    if not source.exists():
        raise GenerationError("R11A artifact validator R3 source is absent")
    text = source.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    FrozenObject,\n    NumberToken,\n    strict_json_loads,\n)",
        "    FrozenObject,\n    NumberToken,\n    canonical_json_bytes,\n    strict_json_loads,\n)",
        "artifact canonical bytes import",
    )
    text = replace_once(
        text,
        '''                    row_id = __import__("hashlib").sha256(
                        json.dumps(row.to_plain(), sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
''',
        '''                    row_id = __import__("hashlib").sha256(
                        canonical_json_bytes(row, final_newline=False)
                    ).hexdigest()
''',
        "artifact row identity",
    )
    text = text.replace(
        'print("R11A_EXECUTION_ARTIFACT_R3_VALID_BEFORE_UPLOAD")',
        'print("R11A_EXECUTION_ARTIFACT_R4_VALID_BEFORE_UPLOAD")',
    )
    destination.write_text(text, encoding="utf-8")


def generate_workflow_r6() -> None:
    source = CORRECTIVE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r5.yml"
    destination = CORRECTIVE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml"
    text = source.read_text(encoding="utf-8")
    replacements = {
        "validate_r11a_approval.py": "validate_r11a_approval_r4.py",
        "validate_r11a_role_attestation.py": "validate_r11a_role_attestation_r4.py",
        "validate_r11a_role_preflight_evidence.py": "validate_r11a_role_preflight_evidence_r4.py",
        "validate_r11a_workflow_installation.py": "validate_r11a_workflow_installation_r4.py",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    destination.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = TESTS / "test_archive_inventory_r11a_corrective_artifacts.py"
    text = path.read_text(encoding="utf-8")
    for old in (
        "hyperliquid-archive-r11a-identity-boundary-diagnostic-r3.yml",
        "hyperliquid-archive-r11a-identity-boundary-diagnostic-r4.yml",
        "hyperliquid-archive-r11a-identity-boundary-diagnostic-r5.yml",
    ):
        text = text.replace(
            old,
            "hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml",
        )
    text = text.replace(
        "validate_r11a_corrective_implementation_r4.py --canonical-bytes",
        "validate_r11a_corrective_implementation_r5.py --canonical-bytes",
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_integral_normalizer()
    patch_lz4_line_cap()
    patch_protocol_singletons()
    patch_join_cleanup()
    patch_boundary_validation()
    patch_entrypoint_failure_fallback()
    generate_artifact_validator_r4()
    generate_workflow_r6()
    patch_tests()
    print("R11A_CORRECTIVE_FINAL_R6_FILES_GENERATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
