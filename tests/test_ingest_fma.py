import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from approve import approve  # noqa: E402
from catalog import read_csv, write_tracks  # noqa: E402
from ingest_fma import next_id, parse_track_page  # noqa: E402
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

    def test_next_id(self) -> None:
        self.assertEqual(next_id([]), "fma-0001")
        self.assertEqual(next_id([track(id="fma-0009"), track(id="ia-0050")]), "fma-0010")


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

    def test_refuses_unknown_and_non_pending_ids(self) -> None:
        write_tracks([track()], self.tracks)
        with self.assertRaises(ValueError):
            approve("shane", ["fma-9999"], self.tracks)
        with self.assertRaises(ValueError):
            approve("shane", ["fma-0001"], self.tracks)


if __name__ == "__main__":
    unittest.main()
