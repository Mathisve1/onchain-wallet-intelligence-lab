from __future__ import annotations

import argparse
from pathlib import Path

from .artifact_schema import RESULT_FILE, RETURN_CODE_FILE, TERMINAL_RETURN_CODES
from .canonical import FrozenObject, NumberToken, strict_json_loads


class TerminalPropagationError(RuntimeError):
    pass


def _exact_int(value: object, label: str) -> int:
    if isinstance(value, NumberToken) and value.is_integer_token:
        return int(value.token, 10)
    if type(value) is int:
        return value
    raise TerminalPropagationError(f"{label} is not an exact integer")


def validated_terminal_return_code(artifact: Path, captured_rc: Path) -> int:
    result = strict_json_loads((artifact / RESULT_FILE).read_bytes())
    if not isinstance(result, FrozenObject):
        raise TerminalPropagationError("terminal result is not an object")
    terminal = result["terminal_class"]
    if not isinstance(terminal, str) or terminal not in TERMINAL_RETURN_CODES:
        raise TerminalPropagationError("terminal class is unknown")
    result_rc = _exact_int(result["return_code"], "result return code")
    try:
        detached_rc = int(
            (artifact / RETURN_CODE_FILE).read_text(encoding="ascii").strip(),
            10,
        )
        executed_rc = int(captured_rc.read_text(encoding="ascii").strip(), 10)
    except (OSError, UnicodeError, ValueError) as exc:
        raise TerminalPropagationError("terminal return-code evidence is invalid") from exc
    expected = TERMINAL_RETURN_CODES[terminal]
    if result_rc != expected or detached_rc != expected or executed_rc != expected:
        raise TerminalPropagationError("terminal return-code projections disagree")
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--captured-rc", required=True, type=Path)
    args = parser.parse_args(argv)
    return validated_terminal_return_code(args.artifact, args.captured_rc)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["TerminalPropagationError", "validated_terminal_return_code"]
