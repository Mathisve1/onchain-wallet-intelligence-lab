from __future__ import annotations

import argparse
from pathlib import Path

from . import runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--artifact-directory", required=True)
    args = parser.parse_args(argv)
    outcome = runner.execute_network(
        workspace=Path(args.workspace),
        artifact_directory=Path(args.artifact_directory),
    )
    print(outcome.terminal_class)
    return outcome.return_code


if __name__ == "__main__":
    raise SystemExit(main())
