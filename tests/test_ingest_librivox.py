# Python Imports
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

# Local Imports
import ingest_librivox  # noqa: E402
from catalog import COLUMNS, read_csv, write_tracks  # noqa: E402
from ingest_librivox import allowed, audio_frames, frame_len, plan  # noqa: E402

HEADER = bytes([0xFF, 0xFB, 0x50, 0x00])  # MPEG-1 Layer III, 64 kbps, 44.1 kHz: 208-byte frames


def frame(fill: int) -> bytes:
    return HEADER + bytes([fill]) * 204


def mp3(*fills: int, xing: bool = True) -> bytes:
    """An ID3 tag, an optional Xing header frame, audio frames, and an ID3v1 tag."""
    info = HEADER + b"\0" * 32 + b"Xing" + b"\0" * 168 if xing else b""
    return b"ID3\x03\x00\x00\x00\x00\x00\x05hello" + info + b"".join(frame(f) for f in fills) + b"TAG" + b"\0" * 125


class FramesTest(unittest.TestCase):
    def test_frame_len(self) -> None:
        self.assertEqual(frame_len(HEADER), 208)
        self.assertEqual(frame_len(b"ID3\x03"), 0)

    def test_audio_frames_drops_tags_and_the_length_header(self) -> None:
        self.assertEqual(audio_frames(mp3(1, 2)), frame(1) + frame(2))
        self.assertEqual(audio_frames(mp3(3, xing=False)), frame(3))

    def test_audio_frames_refuses_non_mp3(self) -> None:
        with self.assertRaises(ValueError):
            audio_frames(b"<html>not audio</html>")

    def test_plan_keeps_sections_whole(self) -> None:
        blocks = plan([{"playtime": p} for p in (600, 600, 600, 3000, 300)], 1200)
        self.assertEqual([[int(s["playtime"]) for s in b] for b in blocks], [[600, 600], [600], [3000], [300]])

    def test_allowed_hosts(self) -> None:
        self.assertTrue(allowed("https://ia800300.us.archive.org/x.mp3"))
        self.assertTrue(allowed("https://librivox.org/a-book/"))
        for bad in ("http://librivox.org/a/", "https://evil.example/x.mp3", "https://archive.org.evil.example/x"):
            self.assertFalse(allowed(bad), bad)


class IngestTest(unittest.TestCase):
    BOOK = {
        "id": "42", "title": "A Book", "url_librivox": "https://librivox.org/a-book/", "url_iarchive": "https://archive.org/details/a_book",
        "authors": [{"first_name": "Ann", "last_name": "Author"}],
        "sections": [
            {"section_number": "2", "title": "Two", "playtime": "600", "listen_url": "https://archive.org/s2.mp3", "readers": [{"display_name": "Reader B"}]},
            {"section_number": "1", "title": "One", "playtime": "600", "listen_url": "https://archive.org/s1.mp3", "readers": [{"display_name": "Reader A"}]},
            {"section_number": "3", "title": "Three", "playtime": "1500", "listen_url": "https://archive.org/s3.mp3", "readers": [{"display_name": "Reader A"}]},
        ],
    }  # fmt: skip

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "evidence").mkdir()
        write_tracks([], self.root / "tracks.csv")
        self.fetched: list[str] = []

    def fake_get(self, page: str):
        def get(url: str, limit: int) -> bytes:
            self.fetched.append(url)
            if "api/feed" in url:
                return json.dumps({"books": [self.BOOK]}).encode()
            if url == self.BOOK["url_librivox"]:
                return page.encode()
            return mp3(int(url[-5]))  # s1.mp3 -> frames of 1s

        return get

    def run_ingest(self, page: str = "<p>LibriVox recordings are\n Public Domain in the USA.</p>") -> list[str]:
        with unittest.mock.patch.object(ingest_librivox, "get", self.fake_get(page)), unittest.mock.patch.object(
            ingest_librivox, "wayback", lambda url: "https://web.archive.org/web/1/" + url
        ):
            return ingest_librivox.ingest("42", "lilbeats", "fairy-tales", 20, self.root / "staging", self.root / "tracks.csv", self.root / "evidence")

    def test_builds_blocks_rows_and_evidence(self) -> None:
        self.assertEqual(self.run_ingest(), ["lv-42-b01", "lv-42-b02"])
        header, rows = read_csv(self.root / "tracks.csv")
        self.assertEqual(header, COLUMNS)
        first = rows[0]
        self.assertEqual((first["status"], first["license"], first["station"], first["playlists"]), ("pending", "PD", "lilbeats", "fairy-tales"))
        self.assertEqual((first["duration_s"], first["kid_safe"]), ("1200", ""))
        self.assertIn("Reader A, Reader B", first["attribution"])
        ev = json.loads((self.root / "evidence" / "lv-42-b01.json").read_text())
        self.assertEqual((ev["file_sha256"], ev["page_metadata"]["sections"]), (first["sha256"], ["1", "2"]))
        block = (self.root / "staging" / "lv-42-b01.mp3").read_bytes()
        self.assertIn(frame(1) + frame(2), block)  # sections in order, joined with no tags between

    def test_rebuild_is_identical_and_downloads_nothing(self) -> None:
        self.run_ingest()
        before = (self.root / "staging" / "lv-42-b01.mp3").read_bytes()
        self.fetched.clear()
        self.run_ingest()
        self.assertEqual((self.root / "staging" / "lv-42-b01.mp3").read_bytes(), before)
        self.assertFalse([u for u in self.fetched if u.endswith(".mp3")])
        self.assertEqual(len(read_csv(self.root / "tracks.csv")[1]), 2)

    def test_refuses_to_change_reviewed_audio_or_the_split(self) -> None:
        self.run_ingest()
        _, rows = read_csv(self.root / "tracks.csv")
        rows[0].update(status="approved", sha256="0" * 64)  # as if approved from different audio
        write_tracks(rows, self.root / "tracks.csv")
        with self.assertRaisesRegex(ValueError, "already approved"):
            self.run_ingest()
        self.assertTrue((self.root / "staging" / "lv-42-b01.mp3").is_file())  # the reviewed file stays put
        self.BOOK = {**self.BOOK, "sections": self.BOOK["sections"][:2]}
        with self.assertRaisesRegex(ValueError, "retire the old rows"):
            self.run_ingest()

    def test_keeps_catalog_edits_made_while_downloading(self) -> None:
        def approve_meanwhile(url: str) -> str:
            write_tracks([{**dict.fromkeys(COLUMNS, ""), "id": "fma-0001", "status": "approved"}], self.root / "tracks.csv")
            return "https://web.archive.org/web/1/" + url

        with unittest.mock.patch.object(ingest_librivox, "get", self.fake_get("LibriVox recordings are Public Domain in the USA.")), unittest.mock.patch.object(ingest_librivox, "wayback", approve_meanwhile):
            ingest_librivox.ingest("42", "lilbeats", "fairy-tales", 20, self.root / "staging", self.root / "tracks.csv", self.root / "evidence")
        self.assertEqual([r["id"] for r in read_csv(self.root / "tracks.csv")[1]], ["fma-0001", "lv-42-b01", "lv-42-b02"])

    def test_refuses_a_changed_block_approved_while_it_ran(self) -> None:
        self.run_ingest()
        _, rows = read_csv(self.root / "tracks.csv")
        rows[0]["sha256"] = "0" * 64  # pending, but built from different audio: it gets rebuilt
        write_tracks(rows, self.root / "tracks.csv")

        real_sha256 = ingest_librivox.sha256

        def approve_meanwhile(path: Path) -> str:  # the first block is hashed, then I approve it
            _, now = read_csv(self.root / "tracks.csv")
            now[0]["status"] = "approved"
            write_tracks(now, self.root / "tracks.csv")
            return real_sha256(path)

        with unittest.mock.patch.object(ingest_librivox, "get", self.fake_get("LibriVox recordings are Public Domain in the USA.")), unittest.mock.patch.object(
            ingest_librivox, "wayback", lambda url: "https://web.archive.org/web/1/" + url
        ), unittest.mock.patch.object(ingest_librivox, "sha256", approve_meanwhile):
            with self.assertRaisesRegex(ValueError, "reviewed while this ran"):
                ingest_librivox.ingest("42", "lilbeats", "fairy-tales", 20, self.root / "staging", self.root / "tracks.csv", self.root / "evidence")
        ids = [r["id"] for r in read_csv(self.root / "tracks.csv")[1]]
        self.assertEqual(ids, ["lv-42-b01", "lv-42-b02"])

    def test_refuses_a_page_without_the_public_domain_line(self) -> None:
        with self.assertRaisesRegex(ValueError, "public-domain line"):
            self.run_ingest(page="<p>All rights reserved.</p>")


if __name__ == "__main__":
    unittest.main()
