import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from tag_mp3 import _frame, _syncsafe, _split, read_tags, tag  # noqa: E402

AUDIO = b"\xff\xfb\x90\x64" + b"\x00" * 400


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
                art = _frame(b"APIC", b"\x00image/jpeg\x00\x03\x00JPEGDATA", major)
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


if __name__ == "__main__":
    unittest.main()
