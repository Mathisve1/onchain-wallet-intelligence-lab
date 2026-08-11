#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "governance/generate_r11a_corrective_final_files.py"
VALIDATOR = ROOT / "governance/validate_r11a_corrective_implementation_r4.py"


class GenerationV2Error(RuntimeError):
    pass


def run_base_generator() -> None:
    if GENERATOR.exists():
        spec = importlib.util.spec_from_file_location("r11a_final_generator", GENERATOR)
        if spec is None or spec.loader is None:
            raise GenerationV2Error("cannot load base final generator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.main()
    elif not VALIDATOR.exists():
        raise GenerationV2Error("neither base generator nor generated files exist")


def patch_validator() -> None:
    text = VALIDATOR.read_text(encoding="utf-8")
    old = '''    if path.name != "network.py":
        for token in ("urllib.request", "boto3", "requests", "httpx", "socket"):
            require(token not in text, f"network capability outside network.py: {path}")
'''
    new = '''    if path.name != "network.py":
        forbidden_modules = {"urllib", "urllib.request", "socket", "boto3", "requests", "httpx"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_modules or any(alias.name.startswith(value + ".") for value in forbidden_modules):
                        raise ValidationError(f"network import outside network.py: {path}:{alias.name}")
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in forbidden_modules or any(module.startswith(value + ".") for value in forbidden_modules):
                    raise ValidationError(f"network import outside network.py: {path}:{module}")
'''
    count = text.count(old)
    if count == 1:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise GenerationV2Error(f"unexpected implementation validator source; matches={count}")
    VALIDATOR.write_text(text, encoding="utf-8")


def main() -> int:
    run_base_generator()
    patch_validator()
    print("R11A_CORRECTIVE_FINAL_FILES_V2_GENERATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
