import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from catalog import read_csv, write_tracks  # noqa: E402
from export_credits import export_credits  # noqa: E402
from export_playlist import export_playlists  # noqa: E402
from hash_files import hash_files, sha256  # noqa: E402
from test_validate import track  # noqa: E402


class IngestScriptsTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.tracks = self.dir / "tracks.csv"
        self.evidence = self.dir / "evidence"
        self.evidence.mkdir()
        self.media = self.dir / "media" / "lofi" / "lofi-day"
        self.media.mkdir(parents=True)

    def test_hash_fills_csv_and_empty_evidence_hash(self) -> None:
        (self.media / "fma-0001.mp3").write_bytes(b"audio")
        write_tracks([track(status="pending", sha256="")], self.tracks)
        (self.evidence / "fma-0001.json").write_text(json.dumps({"id": "fma-0001", "file_sha256": ""}))
        self.assertEqual(hash_files(self.dir / "media", self.tracks, self.evidence), [])
        digest = sha256(self.media / "fma-0001.mp3")
        self.assertEqual(read_csv(self.tracks)[1][0]["sha256"], digest)
        self.assertEqual(json.loads((self.evidence / "fma-0001.json").read_text())["file_sha256"], digest)

    def test_hash_never_overwrites_an_approved_tracks_hash(self) -> None:
        (self.media / "fma-0001.mp3").write_bytes(b"swapped audio")
        write_tracks([track()], self.tracks)
        problems = hash_files(self.dir / "media", self.tracks, self.evidence)
        self.assertTrue(any("changed since it was approved" in p for p in problems))
        self.assertEqual(read_csv(self.tracks)[1][0]["sha256"], track()["sha256"])

    def test_hash_reports_missing_files(self) -> None:
        write_tracks([track(status="pending")], self.tracks)
        self.assertTrue(any("not found" in p for p in hash_files(self.dir / "media", self.tracks, self.evidence)))

    def test_hash_skips_symlinks(self) -> None:
        outside = self.dir / "outside.mp3"
        outside.write_bytes(b"not station media")
        (self.media / "fma-0001.mp3").symlink_to(outside)
        write_tracks([track(status="pending", sha256="")], self.tracks)
        self.assertTrue(any("not found" in p for p in hash_files(self.dir / "media", self.tracks, self.evidence)))

    def test_hash_reports_evidence_for_a_different_file(self) -> None:
        (self.media / "fma-0001.mp3").write_bytes(b"audio")
        write_tracks([track(status="pending", sha256="")], self.tracks)
        (self.evidence / "fma-0001.json").write_text(json.dumps({"id": "fma-0001", "file_sha256": "b" * 64}))
        problems = hash_files(self.dir / "media", self.tracks, self.evidence)
        self.assertTrue(any("different file" in p for p in problems))
        self.assertEqual(json.loads((self.evidence / "fma-0001.json").read_text())["file_sha256"], "b" * 64)

    def test_credits_order_and_special_characters(self) -> None:
        write_tracks(
            [
                track(id="fma-0003", file_name="fma-0003.mp3", artist="b", title="Same"),
                track(id="fma-0002", file_name="fma-0002.mp3", artist="A", title="Same"),
                track(id="fma-0001", file_name="fma-0001.mp3", artist="a", title="Same", attribution='"Café <b>&</b>" by a'),
            ],
            self.tracks,
        )
        path = export_credits(self.tracks, self.dir / "out")
        credits = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([c["id"] for c in credits], ["fma-0001", "fma-0002", "fma-0003"])
        self.assertEqual(credits[0]["attribution"], '"Café <b>&</b>" by a')
        self.assertIn("Café", path.read_text(encoding="utf-8"))

    def test_exports_include_only_approved_tracks(self) -> None:
        write_tracks(
            [
                track(),
                track(id="fma-0002", file_name="fma-0002.mp3", status="pending"),
                track(id="fma-0003", file_name="fma-0003.mp3", playlists="lofi-day;lofi-night"),
            ],
            self.tracks,
        )
        out = self.dir / "out"
        credits = json.loads(export_credits(self.tracks, out).read_text())
        self.assertEqual([c["id"] for c in credits], ["fma-0001", "fma-0003"])
        self.assertEqual(credits[0]["station"], "lofi")
        paths = export_playlists(self.tracks, out)
        self.assertEqual([p.relative_to(out).as_posix() for p in paths], ["lofi/lofi-day.m3u", "lofi/lofi-night.m3u"])
        self.assertEqual(paths[0].read_text(), "#EXTM3U\nfma-0001.mp3\nfma-0003.mp3\n")


class CommandLineTest(unittest.TestCase):
    """Runs the scripts as Shane would, against a throwaway copy of the repo layout."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(Path(__file__).resolve().parent.parent / "scripts", self.root / "scripts")
        (self.root / "catalog").mkdir()
        (self.root / "evidence").mkdir()
        (self.root / "catalog" / "sources.csv").write_text("key,name,url,license_terms_url,notes\nfma,FMA,https://example.org,,\n")

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, *args], cwd=self.root, capture_output=True, text=True)

    def test_exports_refuse_an_invalid_catalog(self) -> None:
        write_tracks([track()], self.root / "catalog" / "tracks.csv")  # approved with no evidence
        for script in ("scripts/export_credits.py", "scripts/export_playlist.py"):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 1)
                self.assertIn("fails validate.py", result.stderr)
        self.assertFalse((self.root / "out").exists())

    def test_valid_catalog_exits_zero(self) -> None:
        write_tracks([track(status="pending")], self.root / "catalog" / "tracks.csv")
        for script in ("scripts/validate.py", "scripts/export_credits.py", "scripts/export_playlist.py"):
            with self.subTest(script=script):
                self.assertEqual(self.run_script(script).returncode, 0)

    def test_validate_and_hash_exit_codes(self) -> None:
        write_tracks([track(status="pending", license="CC-BY-NC-4.0")], self.root / "catalog" / "tracks.csv")
        self.assertEqual(self.run_script("scripts/validate.py").returncode, 1)
        self.assertEqual(self.run_script("scripts/hash_files.py").returncode, 1)  # no media folder given
        media = self.root / "media"
        media.mkdir()
        self.assertEqual(self.run_script("scripts/hash_files.py", str(media)).returncode, 1)  # file missing
        (media / "fma-0001.mp3").write_bytes(b"audio")
        self.assertEqual(self.run_script("scripts/hash_files.py", str(media)).returncode, 0)


if __name__ == "__main__":
    unittest.main()
