import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from approve import approve  # noqa: E402
from catalog import read_csv, write_tracks  # noqa: E402
import ingest_fma  # noqa: E402
from ingest_fma import check_url, cover_url, looks_like_mp3, next_id, page_metadata, parse_track_page  # noqa: E402
from test_validate import track  # noqa: E402

URL = "https://freemusicarchive.org/music/popoi/single/cafezinho-com-leite/"


def page(licence: str = "licenses/by/4.0", url: str = URL, album: str = "-") -> str:
    info = (
        '{"id":1,"url":"' + url.replace("/", "\\/") + '","title":"Caf&eacute; Song","artistName":"Popoi",'
        '"albumTitle":"' + album + '","fileUrl":"https:\\/\\/files.example\\/x.mp3"}'
    )
    return (
        f"<div data-track-info='{info}'></div>"
        f'<div><a rel="license" class="x" href="https://creativecommons.org/{licence}"><img/></a>'
        '<span>Caf&eacute; Song</span> by <a>Popoi</a> is licensed under a <a>Attribution 4.0 International License</a>.</div>'
    )


class ParseTrackPageTest(unittest.TestCase):
    def test_reads_track_and_licence(self) -> None:
        t = parse_track_page(page(), URL)
        self.assertEqual((t["title"], t["artist"], t["album"]), ("Café Song", "Popoi", ""))
        self.assertEqual((t["license"], t["license_url"]), ("CC-BY-4.0", "https://creativecommons.org/licenses/by/4.0/"))
        self.assertEqual(t["attribution"], '"Café Song" by Popoi, CC BY 4.0')
        self.assertEqual(t["quote"], "Café Song by Popoi is licensed under a Attribution 4.0 International License.")
        self.assertEqual(t["file_url"], "https://files.example/x.mp3")

    def test_maps_sa_nd_and_cc0(self) -> None:
        self.assertEqual(parse_track_page(page("licenses/by-sa/3.0"), URL)["license"], "CC-BY-SA-3.0")
        self.assertEqual(parse_track_page(page("licenses/by-nd/4.0"), URL)["license"], "CC-BY-ND-4.0")
        self.assertEqual(parse_track_page(page("publicdomain/zero/1.0"), URL)["license"], "CC0-1.0")

    def test_refuses_nc_and_missing_licences(self) -> None:
        for licence in ("licenses/by-nc/4.0", "licenses/by-nc-sa/4.0", "licenses/by-nc-nd/4.0"):
            with self.subTest(licence=licence), self.assertRaises(ValueError):
                parse_track_page(page(licence), URL)
        with self.assertRaises(ValueError):
            parse_track_page(page().replace('rel="license"', 'rel="other"'), URL)

    def test_refuses_a_page_whose_track_data_is_for_another_url(self) -> None:
        with self.assertRaises(ValueError):
            parse_track_page(page(url="https://freemusicarchive.org/music/other/track/"), URL)

    def test_refuses_a_page_with_more_than_one_licence(self) -> None:
        footer = '<footer><a rel="license" href="https://creativecommons.org/licenses/by-nc/4.0">site</a></footer>'
        with self.assertRaises(ValueError):
            parse_track_page(page() + footer, URL)

    def test_page_metadata(self) -> None:
        extra = (
            '<a href="https://freemusicarchive.org/genre/Lo-fi_Hip-Hop/">Lo-fi Hip-Hop</a>'
            '<a href="https://freemusicarchive.org/genre/Chill-out/"> Chill-out </a>'
            "<span>Released</span> <span>Sep 29, 2025</span>"
            '<img src="https://freemusicarchive.org/image/?file=artist_image%2Fa.jpg&amp;type=artist">'
            '<img src="https://freemusicarchive.org/image/?file=image%2Fb.png&amp;width=290&amp;type=album">'
            '<img src="https://freemusicarchive.org/image/?file=image%2Fb.png&amp;width=400&amp;type=album">'
        )
        m = page_metadata(page() + extra)
        self.assertEqual(m["genres"], ["Lo-fi Hip-Hop", "Chill-out"])
        self.assertEqual(m["released"], "2025-09-29")
        self.assertEqual(m["art_url"], "https://freemusicarchive.org/image/?file=image%2Fb.png&width=400&type=album")
        self.assertEqual(page_metadata(page()), {"genres": [], "released": "", "art_url": ""})

    def test_cover_prefers_the_track_image(self) -> None:
        links = (
            '"https://freemusicarchive.org/image/?file=image%2Falbum.png&amp;width=400&amp;type=album"'
            '"https://freemusicarchive.org/image/?file=track_image%2Ft.png&amp;width=290&amp;type=track"'
        )
        self.assertIn("track_image", cover_url(links))

    def test_looks_like_mp3(self) -> None:
        self.assertTrue(looks_like_mp3(b"ID3\x03\x00"))
        self.assertTrue(looks_like_mp3(b"\xff\xfb\x90\x64"))
        for not_mp3 in (b"<html>", b"PK\x03\x04", b"\x89PNG", b"", b"\xff"):
            self.assertFalse(looks_like_mp3(not_mp3))

    def test_next_id(self) -> None:
        self.assertEqual(next_id([]), "fma-0001")
        self.assertEqual(next_id([track(id="fma-0009"), track(id="ia-0050")]), "fma-0010")


class FakeResponse:
    def __init__(self, body: bytes, url: str, kind: str = "audio/mpeg") -> None:
        self.body, self.url = body, url
        self.headers = type("H", (), {"get_content_type": lambda _self: kind})()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def geturl(self) -> str:
        return self.url

    def read(self, n: int) -> bytes:
        chunk, self.body = self.body[:n], self.body[n:]
        return chunk


class FetchTest(unittest.TestCase):
    AUDIO = "https://files.freemusicarchive.org/storage/x.mp3"

    def fake(self, response: FakeResponse) -> None:
        original = ingest_fma.urllib.request.urlopen
        ingest_fma.urllib.request.urlopen = lambda *a, **k: response
        self.addCleanup(setattr, ingest_fma.urllib.request, "urlopen", original)

    def test_check_url_allows_only_https_on_listed_hosts(self) -> None:
        check_url(self.AUDIO, ingest_fma.AUDIO_HOSTS)
        for bad in ("file:///etc/passwd", "http://files.freemusicarchive.org/x.mp3", "https://evil.example/x.mp3", "ftp://files.freemusicarchive.org/x"):
            with self.subTest(url=bad), self.assertRaises(ValueError):
                check_url(bad, ingest_fma.AUDIO_HOSTS)

    def test_fetch_returns_body_and_type(self) -> None:
        self.fake(FakeResponse(b"ID3audio", self.AUDIO))
        self.assertEqual(ingest_fma.fetch(self.AUDIO, ingest_fma.AUDIO_HOSTS), (b"ID3audio", "audio/mpeg"))

    def test_fetch_refuses_a_redirect_off_the_allowed_hosts(self) -> None:
        self.fake(FakeResponse(b"x", "https://evil.example/x.mp3"))
        with self.assertRaises(ValueError):
            ingest_fma.fetch(self.AUDIO, ingest_fma.AUDIO_HOSTS)

    def test_fetch_refuses_bodies_over_the_cap(self) -> None:
        self.fake(FakeResponse(b"x" * 3_000_000, self.AUDIO))
        with self.assertRaises(ValueError):
            ingest_fma.fetch(self.AUDIO, ingest_fma.AUDIO_HOSTS, limit=2_000_000)


class ApproveTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tracks = Path(tmp.name) / "tracks.csv"

    def test_refuses_and_rolls_back_when_validation_fails(self) -> None:
        write_tracks([track(status="pending", reviewed_by="")], self.tracks)
        with self.assertRaises(ValueError):
            approve("shane", ["fma-0001"], self.tracks)  # no evidence file, so validation fails
        self.assertEqual(read_csv(self.tracks)[1][0]["status"], "pending")

    def test_refuses_evidence_with_a_failed_wayback_save(self) -> None:
        root = self.tracks.parent
        (root / "sources.csv").write_text("key,name,url,license_terms_url,notes\nfma,FMA,https://example.org,,\n")
        (root / "evidence").mkdir()
        ev = {
            "id": "fma-0001", "source_url": "https://example.org/track", "license": "CC-BY-4.0",
            "license_text_quote": "Licensed CC BY 4.0", "archived_url": "",
            "captured_at": "2026-10-19T21:00:00Z", "file_sha256": "a" * 64,
        }  # fmt: skip
        (root / "evidence" / "fma-0001.json").write_text(json.dumps(ev))
        write_tracks([track(status="pending", reviewed_by="")], self.tracks)
        with self.assertRaisesRegex(ValueError, "Wayback save failed"):
            approve("shane", ["fma-0001"], self.tracks, root / "sources.csv", root / "evidence")
        self.assertEqual(read_csv(self.tracks)[1][0]["status"], "pending")
        ev["archived_url"] = "https://web.archive.org/web/1/https://example.org/track"
        (root / "evidence" / "fma-0001.json").write_text(json.dumps(ev))
        self.assertEqual(approve("shane", ["fma-0001"], self.tracks, root / "sources.csv", root / "evidence"), ["fma-0001.mp3"])

    def test_refuses_unknown_and_non_pending_ids(self) -> None:
        write_tracks([track()], self.tracks)
        with self.assertRaises(ValueError):
            approve("shane", ["fma-9999"], self.tracks)
        with self.assertRaises(ValueError):
            approve("shane", ["fma-0001"], self.tracks)


if __name__ == "__main__":
    unittest.main()
