import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from catalog import COLUMNS, read_csv, write_tracks  # noqa: E402
import ingest_ccmixter  # noqa: E402
from ingest_ccmixter import parse_upload_page  # noqa: E402
from test_validate import track  # noqa: E402
from validate import validate  # noqa: E402

URL = "https://ccmixter.org/files/cdk/17432"
SAMPLE = (Path(__file__).parent / "samples" / "ccmixter-upload.html").read_text(encoding="utf-8")
MP3 = "https://ccmixter.org/content/cdk/cdk_-_Silence_Await.mp3"


def page(licence: str = "licenses/by/3.0") -> str:
    return SAMPLE.replace("licenses/by/3.0", licence)


class ParseUploadPageTest(unittest.TestCase):
    def test_reads_upload_and_licence(self) -> None:
        t = parse_upload_page(SAMPLE, URL)
        self.assertEqual((t["title"], t["artist"]), ("Silence Await", "cdk"))
        self.assertEqual((t["license"], t["license_url"]), ("CC-BY-3.0", "https://creativecommons.org/licenses/by/3.0/"))
        self.assertEqual(t["attribution"], '"Silence Await" by cdk, CC BY 3.0')
        self.assertEqual(t["quote"], '"Silence Await" by cdk 2008 - Licensed under Creative Commons Attribution (3.0) '
                                     "Click here for how to give credit and other conditions.")  # fmt: skip
        self.assertEqual((t["file_url"], t["released"]), (MP3, "2008-10-27"))

    def test_maps_sa_nd_cc0_and_public_domain(self) -> None:
        for licence, expected in (
            ("licenses/by-sa/2.5", "CC-BY-SA-2.5"), ("licenses/by-nd/4.0", "CC-BY-ND-4.0"),
            ("publicdomain/zero/1.0", "CC0-1.0"), ("publicdomain/mark/1.0", "PD"), ("licenses/publicdomain", "PD"),
        ):  # fmt: skip
            with self.subTest(licence=licence):
                self.assertEqual(parse_upload_page(page(licence), URL)["license"], expected)
        self.assertEqual(parse_upload_page(page("publicdomain/zero/1.0"), URL)["attribution"], '"Silence Await" by cdk, CC0')

    def test_refuses_nc_sampling_plus_and_others(self) -> None:
        for licence in ("licenses/by-nc/3.0", "licenses/by-nc-sa/3.0", "licenses/sampling+/1.0",
                        "licenses/nc-sampling+/1.0", "licenses/sampling/1.0", "licenses/by/3.0/us", "licenses/by/1.0"):  # fmt: skip
            with self.subTest(licence=licence), self.assertRaises(ValueError):
                parse_upload_page(page(licence), URL)
        with self.assertRaises(ValueError):
            parse_upload_page(SAMPLE.replace('rel="license"', 'rel="other"'), URL)
        with self.assertRaises(ValueError):
            parse_upload_page(SAMPLE.replace("creativecommons.org", "example.org"), URL)

    def test_refuses_a_page_with_more_than_one_licence(self) -> None:
        extra = '<a rel="license" href="http://creativecommons.org/licenses/by-nc/3.0/">x</a>'
        with self.assertRaises(ValueError):
            parse_upload_page(SAMPLE + extra, URL)

    def test_refuses_a_licence_box_or_mp3_for_another_upload(self) -> None:
        with self.assertRaises(ValueError):
            parse_upload_page(SAMPLE, "https://ccmixter.org/files/oldDog/17322")
        with self.assertRaises(ValueError):
            parse_upload_page(SAMPLE.replace("_ep_17432", "_ep_17322"), URL)


class IngestTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "evidence").mkdir()
        (self.root / "sources.csv").write_text("key,name,url,license_terms_url,notes\nfma,FMA,x,,\nccmixter,ccMixter,x,,\n")
        self.tracks = self.root / "tracks.csv"
        write_tracks([track(id="ccm-0002", source="ccmixter", source_url="https://ccmixter.org/files/a/1", status="pending", reviewed_by="", file_name="ccm-0002.mp3")], self.tracks)
        self.fetched: list[tuple[str, dict | None]] = []

        def fetch(url, hosts, limit=0, headers=None):
            self.fetched.append((url, headers))
            return (SAMPLE.encode(), "text/html") if url == URL else (b"ID3\x03\x00audio", "audio/mpeg")

        for patch in (
            unittest.mock.patch.object(ingest_ccmixter, "TRACKS", self.tracks),
            unittest.mock.patch.object(ingest_ccmixter, "EVIDENCE", self.root / "evidence"),
            unittest.mock.patch.object(ingest_ccmixter, "fetch", fetch),
            unittest.mock.patch.object(ingest_ccmixter, "tag", lambda *a: None),
            unittest.mock.patch.object(ingest_ccmixter, "wayback", lambda u: "https://web.archive.org/web/1/" + u),
        ):  # fmt: skip
            patch.start()
            self.addCleanup(patch.stop)

    def test_writes_a_pending_row_and_evidence_that_validate(self) -> None:
        self.assertEqual(ingest_ccmixter.ingest(URL, "velvetstatic", "velvetstatic", self.root / "staging"),
                         "ccm-0003: cdk - Silence Await [CC-BY-3.0]")  # fmt: skip
        self.assertEqual(self.fetched, [(URL, None), (MP3, {"Referer": URL})])
        row = read_csv(self.tracks)[1][-1]
        self.assertEqual((row["id"], row["source"], row["status"], row["file_name"]), ("ccm-0003", "ccmixter", "pending", "ccm-0003.mp3"))
        self.assertEqual(list(row), COLUMNS)
        ev = json.loads((self.root / "evidence" / "ccm-0003.json").read_text())
        self.assertEqual((ev["license"], ev["file_sha256"]), ("CC-BY-3.0", row["sha256"]))
        self.assertTrue((self.root / "staging" / "ccm-0003.mp3").is_file())
        self.assertEqual(validate(self.tracks, self.root / "sources.csv", self.root / "evidence"), [])
        self.assertTrue(ingest_ccmixter.ingest(URL, "velvetstatic", "velvetstatic", self.root / "staging").startswith("skip"))

    def test_refuses_audio_that_isnt_mp3(self) -> None:
        with unittest.mock.patch.object(ingest_ccmixter, "fetch", lambda url, *a, **k: (SAMPLE.encode(), "text/html")):
            with self.assertRaisesRegex(ValueError, "not MP3"):
                ingest_ccmixter.ingest(URL, "velvetstatic", "velvetstatic", self.root / "staging")
        self.assertEqual(len(read_csv(self.tracks)[1]), 1)


if __name__ == "__main__":
    unittest.main()
