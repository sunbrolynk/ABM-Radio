# Python Imports
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

# Local Imports
from catalog import read_csv, write_tracks  # noqa: E402
from tag_mp3 import _frame, _split, _syncsafe, apic_image, fix_approved_art, image_mime, licence_name, read_tags, tag  # noqa: E402
from test_validate import track  # noqa: E402

AUDIO = b"\xff\xfb\x90\x64" + b"\x00" * 400
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-data"
PNG = b"\x89PNG\r\n\x1a\n" + b"png-data"
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"webp-data"


def with_tag(frames: bytes, major: int = 3) -> bytes:
    return b"ID3" + bytes([major, 0, 0]) + _syncsafe(len(frames)) + frames + AUDIO


class TagTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "fma-0001.mp3"

    def test_tags_an_untagged_file_and_keeps_the_audio(self) -> None:
        self.path.write_bytes(AUDIO)
        tag(self.path, "Café Song", "Popoi", "Singles", '"Café Song" by Popoi, CC BY 4.0')
        self.assertEqual(read_tags(self.path), {"TIT2": "Café Song", "TPE1": "Popoi", "TALB": "Singles"})
        self.assertTrue(self.path.read_bytes().endswith(AUDIO))
        self.assertEqual(_split(self.path.read_bytes())[2], AUDIO)

    def test_replaces_old_text_but_keeps_other_frames_in_both_versions(self) -> None:
        for major in (3, 4):
            with self.subTest(major=major):
                art = _frame(b"APIC", b"\x00image/jpeg\x00\x03\x00" + JPEG, major)
                old = _frame(b"TIT2", b"\x00Old Title", major)
                self.path.write_bytes(with_tag(art + old, major))
                tag(self.path, "New", "Artist", "", "credit")
                major_out, frames, audio = _split(self.path.read_bytes())
                self.assertEqual(major_out, major)
                self.assertIn(art, [raw for _, raw in frames])
                self.assertEqual([fid for fid, _ in frames].count(b"TIT2"), 1)
                self.assertEqual(read_tags(self.path)["TIT2"], "New")
                self.assertNotIn("TALB", read_tags(self.path))
                self.assertEqual(audio, AUDIO)

    def test_tagging_twice_is_stable(self) -> None:
        self.path.write_bytes(AUDIO)
        tag(self.path, "A", "B", "C", "D")
        first = self.path.read_bytes()
        tag(self.path, "A", "B", "C", "D")
        self.assertEqual(self.path.read_bytes(), first)

    def test_writes_the_extras_and_adds_art_only_when_missing(self) -> None:
        extra = {
            "genres": ["Lo-fi Hip-Hop", "Chill-out"], "released": "2025-09-29", "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_url": "https://freemusicarchive.org/music/a/b/c/", "art": JPEG,
        }  # fmt: skip
        self.path.write_bytes(AUDIO)
        tag(self.path, "T", "Ketsa", "", "credit", extra)
        tags = read_tags(self.path)
        self.assertEqual(tags["TCON"], "Lo-fi Hip-Hop, Chill-out")
        self.assertEqual(tags["TYER"], "2025")
        self.assertEqual(tags["TCOP"], "2025 Ketsa. CC BY 4.0")
        self.assertEqual(tags["WCOP"], "https://creativecommons.org/licenses/by/4.0/")
        self.assertEqual(tags["WOAS"], "https://freemusicarchive.org/music/a/b/c/")
        self.assertEqual(tags["APIC"], "image/jpeg")
        first = self.path.read_bytes()
        tag(self.path, "T", "Ketsa", "", "credit", {**extra, "art": PNG})
        self.assertEqual(self.path.read_bytes(), first)  # the existing cover is kept, never replaced

    def test_image_types_come_from_the_bytes(self) -> None:
        self.assertEqual(image_mime(JPEG), "image/jpeg")
        self.assertEqual(image_mime(PNG), "image/png")
        self.assertEqual(image_mime(WEBP), "")
        self.assertEqual(image_mime(b""), "")

    def test_a_webp_cover_is_never_embedded(self) -> None:
        self.path.write_bytes(AUDIO)
        tag(self.path, "T", "A", "", "c", {"art": WEBP})
        self.assertNotIn("APIC", read_tags(self.path))

    def test_a_broken_cover_is_replaced_but_a_good_one_kept(self) -> None:
        for major in (3, 4):
            with self.subTest(major=major):
                broken = _frame(b"APIC", b"\x00image/jpeg\x00\x03\x00" + WEBP, major)
                self.path.write_bytes(with_tag(broken, major))
                tag(self.path, "T", "A", "", "c", {"art": PNG})
                self.assertEqual(read_tags(self.path)["APIC"], "image/png")

    def test_apic_image_handles_utf16_descriptions(self) -> None:
        raw = _frame(b"APIC", b"\x01image/png\x00\x03" + "Cover".encode("utf-16") + b"\x00\x00" + PNG, 3)
        self.assertEqual(apic_image(raw), PNG)

    def test_v24_files_get_a_full_release_date(self) -> None:
        self.path.write_bytes(with_tag(_frame(b"TPE2", b"\x00x", 4), 4))
        tag(self.path, "T", "A", "", "c", {"released": "2025-09-29"})
        self.assertEqual(read_tags(self.path)["TDRC"], "2025-09-29")

    def test_licence_names(self) -> None:
        cases = {"CC-BY-4.0": "CC BY 4.0", "CC-BY-SA-3.0": "CC BY-SA 3.0", "CC-BY-NC-ND-4.0": "CC BY-NC-ND 4.0", "CC0-1.0": "CC0 1.0", "PD": "Public Domain"}
        for given, expected in cases.items():
            self.assertEqual(licence_name(given), expected)


class FixApprovedArtTest(unittest.TestCase):
    def test_only_the_cover_changes_and_the_hash_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            staging, evidence = root / "staging", root / "evidence"
            staging.mkdir(), evidence.mkdir()
            f = staging / "fma-0001.mp3"
            f.write_bytes(with_tag(_frame(b"APIC", b"\x00image/jpeg\x00\x03\x00" + WEBP, 3)))
            (staging / "fma-0001.art").write_bytes(JPEG)
            (evidence / "fma-0001.json").write_text(json.dumps({"file_sha256": "x", "page_metadata": {}}))
            write_tracks([track()], root / "tracks.csv")
            self.assertEqual(fix_approved_art(staging, root / "tracks.csv", evidence), ["fma-0001"])
            self.assertEqual(_split(f.read_bytes())[2], AUDIO)
            self.assertEqual(read_tags(f)["APIC"], "image/jpeg")
            row = read_csv(root / "tracks.csv")[1][0]
            self.assertEqual(row["status"], "approved")
            self.assertEqual(json.loads((evidence / "fma-0001.json").read_text())["file_sha256"], row["sha256"])
            self.assertIn("audio unchanged", row["notes"])
            self.assertEqual(fix_approved_art(staging, root / "tracks.csv", evidence), [])  # nothing left to fix

            f.write_bytes(with_tag(b""))  # an approved file with no cover at all gets one added
            self.assertEqual(fix_approved_art(staging, root / "tracks.csv", evidence), ["fma-0001"])
            self.assertEqual(read_tags(f)["APIC"], "image/jpeg")
            self.assertEqual(_split(f.read_bytes())[2], AUDIO)
            self.assertEqual(read_csv(root / "tracks.csv")[1][0]["notes"].count("Cover art replaced"), 1)


if __name__ == "__main__":
    unittest.main()
