"""Runs collate-changelog.py against a throwaway copy of the repo layout."""

# Python Imports
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "collate-changelog.py"
CHANGELOG = """# Changelog

## [Unreleased]

### Fixed

- **Old fix:** already here.

### Added

- **Old feature:** already here.

## [0.1.0] - 2026-01-01

### Added

- **First release.**
"""


class CollateChangelogTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "scripts").mkdir()
        shutil.copy(SCRIPT, self.root / "scripts" / SCRIPT.name)
        (self.root / "changelog.d").mkdir()
        (self.root / "changelog.d" / ".gitkeep").touch()
        self.changelog = self.root / "CHANGELOG.md"
        self.changelog.write_text(CHANGELOG)

    def fragment(self, name: str, text: str) -> Path:
        path = self.root / "changelog.d" / name
        path.write_text(text + "\n")
        return path

    def collate(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, f"scripts/{SCRIPT.name}", *args], cwd=self.root, capture_output=True, text=True
        )

    def test_fragments_land_under_their_sections_after_existing_bullets(self) -> None:
        self.fragment("b-thing.added.md", "- **B feature:** second.")
        self.fragment("a-thing.added.md", "- **A feature:** first.")
        self.fragment("c-thing.security.md", "- **Safer:** fixed a hole.")
        self.fragment("d-thing.fixed.md", "- **New fix:** done.")
        result = self.collate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.changelog.read_text(),
            """# Changelog

## [Unreleased]

### Added

- **Old feature:** already here.

- **A feature:** first.

- **B feature:** second.

### Fixed

- **Old fix:** already here.

- **New fix:** done.

### Security

- **Safer:** fixed a hole.

## [0.1.0] - 2026-01-01

### Added

- **First release.**
""",
        )
        self.assertEqual([p.name for p in (self.root / "changelog.d").iterdir()], [".gitkeep"])

    def test_unknown_section_is_refused_and_nothing_changes(self) -> None:
        bad = self.fragment("thing.tweaked.md", "- **Tweak:** x.")
        good = self.fragment("other.added.md", "- **Fine:** y.")
        result = self.collate()
        self.assertEqual(result.returncode, 1)
        self.assertIn("thing.tweaked.md", result.stderr)
        self.assertEqual(self.changelog.read_text(), CHANGELOG)
        self.assertTrue(bad.exists() and good.exists())

    def test_dry_run_prints_but_writes_nothing(self) -> None:
        fragment = self.fragment("thing.changed.md", "- **Changed:** z.")
        result = self.collate("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("### Changed\n\n- **Changed:** z.", result.stdout)
        self.assertEqual(self.changelog.read_text(), CHANGELOG)
        self.assertTrue(fragment.exists())


if __name__ == "__main__":
    unittest.main()
