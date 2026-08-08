from __future__ import annotations

import unittest
from pathlib import Path

from governance.regenerate_manifest import render_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance/REPOSITORY_MANIFEST.sha256"


class RepositoryManifestExactTests(unittest.TestCase):
    def test_manifest_is_byte_exact(self) -> None:
        observed = MANIFEST.read_text(encoding="utf-8")
        expected = render_manifest(ROOT)
        if observed == expected:
            return

        observed_lines = observed.splitlines()
        expected_lines = expected.splitlines()
        observed_set = set(observed_lines)
        expected_set = set(expected_lines)
        missing = [line for line in expected_lines if line not in observed_set]
        extra = [line for line in observed_lines if line not in expected_set]

        details: list[str] = []
        if missing:
            details.append("missing/expected rows:\n" + "\n".join(f"+ {line}" for line in missing))
        if extra:
            details.append("extra/observed rows:\n" + "\n".join(f"- {line}" for line in extra))
        if not missing and not extra:
            details.append("same rows but byte/order/newline representation differs")
        self.fail("repository manifest drift:\n" + "\n".join(details))


if __name__ == "__main__":
    unittest.main()
