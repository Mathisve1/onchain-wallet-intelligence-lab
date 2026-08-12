#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORRECTIVE = ROOT / "research/archive_inventory/r11a_corrective"


class FinalizationError(RuntimeError):
    pass


def replace_definition(path: Path, definition_name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    target = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == definition_name
        ),
        None,
    )
    if target is None or target.end_lineno is None:
        raise FinalizationError(f"definition not found: {path}:{definition_name}")
    lines = text.splitlines(keepends=True)
    start = target.lineno - 1
    while start > 0 and lines[start - 1].lstrip().startswith("@"):
        start -= 1
    lines[start : target.end_lineno] = [replacement.rstrip() + "\n\n"]
    path.write_text("".join(lines), encoding="utf-8")


def patch_canonical() -> None:
    path = CORRECTIVE / "canonical.py"
    text = path.read_text(encoding="utf-8")
    old_alias = 'FrozenValue: TypeAlias = FrozenScalar | "FrozenObject" | tuple["FrozenValue", ...]'
    new_alias = 'FrozenValue: TypeAlias = "FrozenScalar | FrozenObject | tuple[FrozenValue, ...]"'
    if old_alias in text:
        text = text.replace(old_alias, new_alias, 1)
        path.write_text(text, encoding="utf-8")
    elif new_alias not in text:
        raise FinalizationError("recursive FrozenValue alias has unexpected bytes")

    replace_definition(
        path,
        "mathematically_integral_number",
        "\n".join(
            [
                "def mathematically_integral_number(token: NumberToken) -> str | None:",
                '    """Return an exact context-independent base-10 integer string when integral.',
                "",
                "    The implementation never calls ``quantize()`` and therefore does not depend on",
                "    the active Decimal precision. Very large exponent expansions remain bounded.",
                '    """',
                "",
                "    if token.is_integer_token:",
                "        return str(int(token.token, 10))",
                "    try:",
                "        decimal_value = Decimal(token.token)",
                "    except InvalidOperation:",
                "        return None",
                "    if not decimal_value.is_finite():",
                "        return None",
                "    sign, digits_tuple, exponent = decimal_value.as_tuple()",
                '    digits = "".join(str(digit) for digit in digits_tuple) or "0"',
                "    if exponent >= 0:",
                '        expanded = digits + ("0" * exponent)',
                "    else:",
                "        fractional_digits = -exponent",
                "        if fractional_digits > len(digits):",
                "            return None",
                "        split = len(digits) - fractional_digits",
                "        fractional = digits[split:]",
                '        if any(character != "0" for character in fractional):',
                "            return None",
                '        expanded = digits[:split] or "0"',
                '    expanded = expanded.lstrip("0") or "0"',
                "    if len(expanded) > _MAX_NORMALIZED_INTEGER_DIGITS:",
                '        raise CanonicalJSONError("integral JSON number expansion exceeds the frozen bound")',
                '    if sign and expanded != "0":',
                '        return "-" + expanded',
                "    return expanded",
            ]
        ),
    )


def patch_taxonomy_and_artifact() -> None:
    taxonomy = CORRECTIVE / "taxonomy_r4.py"
    text = taxonomy.read_text(encoding="utf-8")
    old = "from collections.abc import Iterator, Mapping, Protocol"
    new = "from collections.abc import Iterator, Mapping\nfrom typing import Protocol"
    if old in text:
        taxonomy.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise FinalizationError("taxonomy Protocol import has unexpected bytes")

    artifact = CORRECTIVE / "artifact_r3.py"
    text = artifact.read_text(encoding="utf-8")
    old = "from .taxonomy_r3 import EvidenceEmitter, TaxonomyResult"
    new = "from .taxonomy_r4 import EvidenceEmitter, TaxonomyResult"
    if old in text:
        artifact.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise FinalizationError("artifact taxonomy import has unexpected bytes")


def patch_sort_evidence() -> None:
    path = CORRECTIVE / "storage.py"
    replace_definition(
        path,
        "SortEvidence",
        "\n".join(
            [
                "@dataclasses.dataclass(frozen=True, slots=True)",
                "class SortEvidence:",
                "    input_records: int",
                "    output_records: int",
                "    input_logical_bytes: int",
                "    output_logical_bytes: int",
                "    source_commitment: dict[str, object]",
                "    destination_commitment: dict[str, object]",
                "    sorted_stream_sha256: str",
                "    output_bytes: int",
                "",
                "    def validate(self) -> None:",
                "        values = (",
                "            self.input_records,",
                "            self.output_records,",
                "            self.input_logical_bytes,",
                "            self.output_logical_bytes,",
                "            self.output_bytes,",
                "        )",
                "        if any(type(value) is not int or value < 0 for value in values):",
                '            raise StorageBoundaryError("sort evidence counts and bytes must be nonnegative integers")',
                "        if self.input_records != self.output_records:",
                '            raise StorageBoundaryError("external sort changed record count")',
                "        if self.input_logical_bytes != self.output_logical_bytes:",
                '            raise StorageBoundaryError("external sort changed logical byte count")',
                '        if int(self.source_commitment.get("record_count", -1)) != self.input_records:',
                '            raise StorageBoundaryError("source commitment record count mismatch")',
                '        if int(self.destination_commitment.get("record_count", -1)) != self.output_records:',
                '            raise StorageBoundaryError("destination commitment record count mismatch")',
                '        if int(self.source_commitment.get("logical_bytes", -1)) != self.input_logical_bytes:',
                '            raise StorageBoundaryError("source commitment logical byte mismatch")',
                '        if int(self.destination_commitment.get("logical_bytes", -1)) != self.output_logical_bytes:',
                '            raise StorageBoundaryError("destination commitment logical byte mismatch")',
                "        if self.source_commitment != self.destination_commitment:",
                '            raise StorageBoundaryError("external sort changed the exact record multiset")',
                "        if len(self.sorted_stream_sha256) != 64:",
                '            raise StorageBoundaryError("sorted stream SHA-256 format invalid")',
                "        if self.output_bytes < self.output_logical_bytes:",
                '            raise StorageBoundaryError("framed output bytes cannot be smaller than logical bytes")',
            ]
        ),
    )

    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "external_sort_partition"
    )
    assignment = next(
        node
        for node in function.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "SortEvidence"
    )
    if assignment.end_lineno is None:
        raise FinalizationError("SortEvidence constructor has no end line")
    replacement = "\n".join(
        [
            "    destination_mapping = destination_commitment.as_mapping()",
            "    evidence = SortEvidence(",
            '        input_records=int(source_commitment["record_count"]),',
            '        output_records=int(destination_mapping["record_count"]),',
            '        input_logical_bytes=int(source_commitment["logical_bytes"]),',
            '        output_logical_bytes=int(destination_mapping["logical_bytes"]),',
            "        source_commitment=source_commitment,",
            "        destination_commitment=destination_mapping,",
            "        sorted_stream_sha256=sorted_stream.hexdigest(),",
            "        output_bytes=destination.stat().st_size,",
            "    )",
        ]
    )
    lines = text.splitlines(keepends=True)
    lines[assignment.lineno - 1 : assignment.end_lineno] = [replacement + "\n"]
    path.write_text("".join(lines), encoding="utf-8")


def patch_tests() -> None:
    path = ROOT / "tests/test_archive_inventory_r11a_corrective_artifacts.py"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "hyperliquid-archive-r11a-identity-boundary-diagnostic-r3.yml":
            "hyperliquid-archive-r11a-identity-boundary-diagnostic-r6.yml",
        "validate_r11a_corrective_implementation.py --approval-eligible":
            "validate_r11a_corrective_implementation_r5.py --canonical-bytes",
    }
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
        elif new not in text:
            raise FinalizationError(f"corrective test expectation has unexpected bytes: {old}")
    path.write_text(text, encoding="utf-8")


def remove_superseded() -> None:
    paths = (
        "research/archive_inventory/r11a_corrective/artifact.py",
        "research/archive_inventory/r11a_corrective/entrypoint.py",
        "research/archive_inventory/r11a_corrective/entrypoint_r3.py",
        "research/archive_inventory/r11a_corrective/entrypoint_r4.py",
        "research/archive_inventory/r11a_corrective/index.py",
        "research/archive_inventory/r11a_corrective/lz4frame.py",
        "research/archive_inventory/r11a_corrective/materialize.py",
        "research/archive_inventory/r11a_corrective/runner.py",
        "research/archive_inventory/r11a_corrective/runner_r3.py",
        "research/archive_inventory/r11a_corrective/taxonomy.py",
        "research/archive_inventory/r11a_corrective/taxonomy_r3.py",
        "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic.yml",
        "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r3.yml",
        "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r4.yml",
        "research/archive_inventory/r11a_corrective/workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r5.yml",
        "governance/r11a_stage_common.py",
        "governance/validate_r11a_corrective_implementation.py",
        "governance/validate_r11a_corrective_implementation_r3.py",
        "governance/validate_r11a_corrective_implementation_r4.py",
        "governance/validate_r11a_execution_artifact.py",
        "governance/validate_r11a_execution_artifact_r3.py",
        "governance/validate_r11a_approval.py",
        "governance/validate_r11a_role_attestation.py",
        "governance/validate_r11a_role_preflight_evidence.py",
        "governance/validate_r11a_workflow_installation.py",
        "governance/validate_r11a_execution_release.py",
        "governance/validate_r11a_execution_release_r3.py",
        "governance/validate_r11a_activation.py",
        "governance/validate_r11a_activation_r3.py",
        "governance/generate_r11a_corrective_final_files.py",
        "governance/generate_r11a_corrective_final_files_v2.py",
        "governance/generate_r11a_corrective_final_files_v3.py",
        "governance/generate_r11a_corrective_final_files_v4.py",
        ".github/workflows/r11a-corrective-finalize-dev.yml",
        ".github/workflows/r11a-corrective-finalize-dev-v2.yml",
        ".github/workflows/r11a-corrective-finalize-dev-v3.yml",
        ".github/workflows/r11a-corrective-finalize-dev-v4.yml",
        ".github/workflows/r11a-corrective-finalize-v5.yml",
        "governance/finalize_r11a_corrective_r6.py",
    )
    for relative in paths:
        candidate = ROOT / relative
        if candidate.exists():
            candidate.unlink()


def main() -> int:
    patch_canonical()
    patch_taxonomy_and_artifact()
    patch_sort_evidence()
    patch_tests()
    remove_superseded()
    print("R11A_CORRECTIVE_R6_PATCHES_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
