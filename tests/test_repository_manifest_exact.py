from __future__ import annotations

import difflib
import unittest
from pathlib import Path

from governance.regenerate_manifest import render_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance/REPOSITORY_MANIFEST.sha256"


class RepositoryManifestExactTests(unittest.TestCase):
    def test_manifest_is_byte_exact(self) -> None:
        observed = MANIFEST.read_text(encoding="utf-8")
        expected = render_manifest(ROOT)
        if observed != expected:
            diff = "".join(
                difflib.unified_diff(
                    observed.splitlines(keepends=True),
                    expected.splitlines(keepends=True),
                    fromfile="observed-manifest",
                    tofile="expected-manifest",
                )
            )
            self.fail("repository manifest drift:\n" + diff)


if __name__ == "__main__":
    unittest.main()
