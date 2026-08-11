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
    tree = ast.parse(text)
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
    new_lines = lines[: target.lineno - 1] + [replacement.rstrip() + "\n\n"] + lines[target.end_lineno :]
    path.write_text("".join(new_lines), encoding="utf-8")


def patch_canonical() -> None:
    replacement = '''def mathematically_integral_number(value: NumberToken) -> str | None:
    """Normalize a mathematical integer without Decimal context or large allocation."""
    token = value.token
    match = _NUMBER_RE.fullmatch(token)
    if match is None:
        return None
    sign, integer_part, fractional_part, exponent_text = match.groups()
    fractional = fractional_part or ""
    exponent = int(exponent_text or "0", 10)
    coefficient = integer_part + fractional
    scale = len(fractional)
    decimal_shift = exponent - scale
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
            suffix = coefficient[cut:]
            if any(character != "0" for character in suffix):
                return None
            digits = coefficient[:cut]
    digits = digits.lstrip("0") or "0"
    if len(digits) > maximum_digits:
        raise CanonicalJSONError("integral decimal token exceeds normalized length cap")
    if sign == "-" and digits != "0":
        return "-" + digits
    return digits
'''
    replace_function(CORRECTIVE / "canonical.py", "mathematically_integral_number", replacement)


def patch_lz4() -> None:
    path = CORRECTIVE / "lz4stream.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '_MASK: Final[int] = 0xFFFFFFFF\n',
        '_MASK: Final[int] = 0xFFFFFFFF\n_MAX_RECORD_BYTES: Final[int] = 16 << 20\n',
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
        "LZ4 bounded line buffer",
    )
    path.write_text(text, encoding="utf-8")


def patch_taxonomy() -> None:
    path = CORRECTIVE / "taxonomy_r4.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''            expected = not overflow and bool(blocks) and all(state.is_expected_pair() for state in blocks.values())
''',
        '''            if occurrences <= 1:
                continue
            expected = not overflow and bool(blocks) and all(state.is_expected_pair() for state in blocks.values())
''',
        "protocol singleton exclusion",
    )
    path.write_text(text, encoding="utf-8")


def generate_artifact_validator() -> None:
    source = GOVERNANCE / "validate_r11a_execution_artifact_r3.py"
    destination = GOVERNANCE / "validate_r11a_execution_artifact_r4.py"
    text = source.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    FrozenObject,
    NumberToken,
    strict_json_loads,
)''',
        '''    FrozenObject,
    NumberToken,
    canonical_json_bytes,
    strict_json_loads,
)''',
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


def generate_workflow() -> None:
    source = CORRECTIVE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r3.yml"
    destination = CORRECTIVE / "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r4.yml"
    text = source.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "python governance/validate_r11a_corrective_implementation.py --approval-eligible",
        "python governance/validate_r11a_corrective_implementation_r4.py --canonical-bytes",
        "workflow immutable implementation validator",
    )
    text = text.replace(
        "research.archive_inventory.r11a_corrective.entrypoint_r3",
        "research.archive_inventory.r11a_corrective.entrypoint_r5",
    )
    text = text.replace(
        "governance/validate_r11a_execution_artifact.py",
        "governance/validate_r11a_execution_artifact_r4.py",
    )
    text = text.replace(
        "validate_r11a_execution_artifact.py'",
        "validate_r11a_execution_artifact_r4.py'",
    )
    destination.write_text(text, encoding="utf-8")


def generate_implementation_validator() -> None:
    source = GOVERNANCE / "validate_r11a_corrective_implementation_r3.py"
    destination = GOVERNANCE / "validate_r11a_corrective_implementation_r4.py"
    text = source.read_text(encoding="utf-8")
    old_tuple = '''EXECUTION_GRAPH = (
    "__init__.py",
    "activity.py",
    "artifact_r3.py",
    "canonical.py",
    "context.py",
    "entrypoint_r3.py",
    "identity.py",
    "index_r3.py",
    "limits.py",
    "lz4stream.py",
    "materialize_r3.py",
    "network.py",
    "parser.py",
    "pricing.py",
    "runner_r3.py",
    "runtime.py",
    "selection.py",
    "storage.py",
    "taxonomy_r3.py",
    "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r4.yml",
)
'''
    new_tuple = '''EXECUTION_GRAPH = (
    "__init__.py",
    "activity.py",
    "artifact_r3.py",
    "canonical.py",
    "context.py",
    "entrypoint_r5.py",
    "identity.py",
    "index_r3.py",
    "join.py",
    "limits.py",
    "lz4stream.py",
    "materialize_r3.py",
    "network.py",
    "parser.py",
    "preflight_artifact.py",
    "pricing.py",
    "runner_r4.py",
    "runtime.py",
    "selection.py",
    "storage.py",
    "taxonomy_r4.py",
    "workflows/hyperliquid-archive-r11a-identity-boundary-diagnostic-r4.yml",
)
'''
    text = replace_once(text, old_tuple, new_tuple, "final execution graph")
    text = text.replace(
        "R11A_CORRECTIVE_R3_IMMUTABLE_IMPLEMENTATION_VALID",
        "R11A_CORRECTIVE_R4_IMMUTABLE_IMPLEMENTATION_VALID",
    )
    destination.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = TESTS / "test_archive_inventory_r11a_corrective_artifacts.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "hyperliquid-archive-r11a-identity-boundary-diagnostic-r3.yml",
        "hyperliquid-archive-r11a-identity-boundary-diagnostic-r4.yml",
    )
    text = text.replace(
        'self.assertIn("validate_r11a_corrective_implementation.py --approval-eligible", text)',
        'self.assertIn("validate_r11a_corrective_implementation_r4.py --canonical-bytes", text)',
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_canonical()
    patch_lz4()
    patch_taxonomy()
    generate_artifact_validator()
    generate_workflow()
    generate_implementation_validator()
    patch_tests()
    print("R11A_CORRECTIVE_FINAL_FILES_GENERATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
