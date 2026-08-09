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
            observed_lines = observed.splitlines(keepends=True)
            expected_lines = expected.splitlines(keepends=True)
            for index, (observed_line, expected_line) in enumerate(zip(observed_lines, expected_lines), start=1):
                if observed_line != expected_line:
                    print(f"FIRST_MANIFEST_MISMATCH_LINE={index}")
                    print(f"OBSERVED_REPR={observed_line!r}")
                    print(f"EXPECTED_REPR={expected_line!r}")
                    print(f"OBSERVED_CODEPOINTS={[ord(ch) for ch in observed_line]}")
                    print(f"EXPECTED_CODEPOINTS={[ord(ch) for ch in expected_line]}")
                    break
            diff = "".join(
                difflib.unified_diff(
                    observed_lines,
                    expected_lines,
                    fromfile="observed-manifest",
                    tofile="expected-manifest",
                )
            )
            self.fail("repository manifest drift:\n" + diff)


if __name__ == "__main__":
    unittest.main()
