"""Runs check-changelog.sh against throwaway repos."""

# Python Imports
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-changelog.sh"
# Git hooks export GIT_DIR and friends; without stripping them, git commands meant for the
# throwaway repo would act on the repo whose hook is running these tests.
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class CheckChangelogTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "someone")
        self.git("config", "user.email", "1+someone@users.noreply.github.com")
        (self.repo / "scripts").mkdir()
        shutil.copy(SCRIPT, self.repo / "scripts" / SCRIPT.name)
        self.commit({"CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n"}, "base")
        self.git("tag", "base")

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, env=ENV)

    def commit(self, files: dict[str, str | None], message: str) -> None:
        for name, text in files.items():
            path = self.repo / name
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", f"scripts/{SCRIPT.name}", "base..HEAD"], cwd=self.repo, capture_output=True, text=True, env=ENV
        )

    def test_fragment_covers_a_product_commit(self) -> None:
        self.commit({"scripts/tool.py": "x = 1\n"}, "add a tool")
        self.commit({"changelog.d/tool.added.md": "- **Tool:** new.\n"}, "describe it")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changelog_edit_still_covers_a_product_commit(self) -> None:
        self.commit({"scripts/tool.py": "x = 1\n", "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n- **Tool.**\n"}, "tool")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_product_commit_without_coverage_fails(self) -> None:
        self.commit({"scripts/tool.py": "x = 1\n"}, "add a tool")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("add a tool", result.stderr)

    def test_misnamed_or_deleted_fragment_is_no_coverage(self) -> None:
        self.commit({"changelog.d/old.added.md": "- **Old.**\n"}, "old fragment")
        self.git("tag", "-f", "base")
        self.commit({"scripts/tool.py": "x = 1\n", "changelog.d/tool.tweaked.md": "- **Tool.**\n"}, "add a tool")
        self.commit({"changelog.d/old.added.md": None}, "drop the old fragment")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_fragment_name_collate_would_refuse_is_no_coverage(self) -> None:
        for name in ("changelog.d/a.b.added.md", "changelog.d/.added.md"):
            with self.subTest(name=name):
                self.commit({"scripts/tool.py": f"x = {name!r}\n", name: "- **Tool.**\n"}, "add a tool")
                result = self.check()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.git("reset", "-q", "--hard", "base")

    def test_fragment_before_the_product_commit_does_not_cover_it(self) -> None:
        self.commit({"changelog.d/tool.added.md": "- **Tool:** new.\n"}, "describe it first")
        self.commit({"scripts/tool.py": "x = 1\n"}, "add a tool")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_merge_that_only_brings_in_another_fragment_does_not_cover(self) -> None:
        self.git("checkout", "-q", "-b", "other")
        self.commit({"changelog.d/other.fixed.md": "- **Other fix.**\n"}, "other branch entry")
        self.git("checkout", "-q", "-")
        self.commit({"scripts/tool.py": "x = 1\n"}, "add a tool")
        self.git("merge", "-q", "--no-edit", "other")
        self.git("tag", "-f", "base", "other")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("add a tool", result.stderr)



if __name__ == "__main__":
    unittest.main()
