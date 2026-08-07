from __future__ import annotations

import argparse
import json
from pathlib import Path

from provider_evidence_builder import evidence_json


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert an ephemeral local signer capture into sanitized offline evidence. No network/provider calls."
    )
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixtures", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.output.exists():
        raise SystemExit("refusing to overwrite existing evidence output")
    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    rendered = evidence_json(capture, args.fixtures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"SANITIZED_SIGNER_EVIDENCE_WRITTEN:{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
