from __future__ import annotations

import difflib
import unittest
from pathlib import Path

import subprocess
import tempfile

from governance.regenerate_manifest import (
    EXCLUDED_NAME_PATTERNS,
    included_files,
    render_manifest,
)

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


    def test_a_run_in_progress_does_not_put_the_manifest_out_of_date(self) -> None:
        """An arm takes hours and writes a checkpoint after every wallet. If
        those files were hashed, the repository would read OUT_OF_DATE for the
        whole run and for as long as a failed run was kept, which would train
        the reader to ignore the one signal that says the tree was altered."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "L2_ARM_A_001.json").write_text("{}", encoding="utf-8")
            (evidence / "L2_ARM_A_001.json.runtime.json").write_text("{}", encoding="utf-8")
            before = render_manifest(root)
            (evidence / "L2_ARM_A_001.json.partial.json").write_text("{}", encoding="utf-8")
            (evidence / "L2_ARM_A_001.json.aborted-7.json").write_text("{}", encoding="utf-8")
            self.assertEqual(render_manifest(root), before)
            # The evidence and its runtime record are hashed; only the
            # transient pair is not.
            names = {path.name for path in included_files(root)}
            self.assertEqual(names, {"L2_ARM_A_001.json", "L2_ARM_A_001.json.runtime.json"})


    def test_every_excluded_pattern_is_also_ignored_by_git(self) -> None:
        """The two exclusions must stay aligned. A pattern the manifest skips
        while git tracks it would be repository content outside the canonical
        file set, which is the one thing the manifest exists to prevent."""
        ignored = {line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
        for pattern in EXCLUDED_NAME_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, ignored)

    def test_no_tracked_file_is_excluded_by_name(self) -> None:
        import fnmatch

        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        for path in tracked:
            name = path.rsplit("/", 1)[-1]
            for pattern in EXCLUDED_NAME_PATTERNS:
                with self.subTest(path=path, pattern=pattern):
                    self.assertFalse(fnmatch.fnmatch(name, pattern), f"{path} is tracked but not hashed")


if __name__ == "__main__":
    unittest.main()
