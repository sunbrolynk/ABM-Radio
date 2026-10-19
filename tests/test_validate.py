import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from catalog import COLUMNS, write_tracks  # noqa: E402
from validate import validate  # noqa: E402

SHA = "a" * 64


def track(**changes: str) -> dict[str, str]:
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        id="fma-0001", station="lofi", title="Morning Coffee", artist="Example Artist", source="fma",
        source_url="https://example.org/track", license="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution='"Morning Coffee" by Example Artist, CC BY 4.0', commercial_ok="yes", streaming_ok="yes",
        downloaded_at="2026-10-19", file_name="fma-0001.mp3", sha256=SHA, playlists="lofi-day",
        status="approved", reviewed_by="shane",
    )  # fmt: skip
    row.update(changes)
    return row


class ValidateTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.tracks = self.dir / "tracks.csv"
        self.evidence = self.dir / "evidence"
        self.evidence.mkdir()
        (self.dir / "sources.csv").write_text("key,name,url,license_terms_url,notes\nfma,FMA,https://example.org,,\n")

    def run_validate(self, *rows: dict[str, str], evidence: dict[str, str] | None = None) -> list[str]:
        write_tracks(list(rows), self.tracks)
        if evidence is not None:
            (self.evidence / f"{evidence['id']}.json").write_text(json.dumps(evidence))
        return validate(self.tracks, self.dir / "sources.csv", self.evidence)

    def good_evidence(self, **changes: str) -> dict[str, str]:
        ev = {
            "id": "fma-0001", "source_url": "https://example.org/track", "license": "CC-BY-4.0",
            "license_text_quote": "Licensed CC BY 4.0", "archived_url": "https://web.archive.org/x",
            "captured_at": "2026-10-19T21:00:00Z", "file_sha256": SHA,
        }  # fmt: skip
        ev.update(changes)
        return ev

    def assertFails(self, errors: list[str], text: str) -> None:
        self.assertTrue(any(text in e for e in errors), f"{text!r} not in {errors}")

    def test_empty_catalog_passes(self) -> None:
        self.assertEqual(self.run_validate(), [])

    def test_approved_track_with_evidence_passes(self) -> None:
        self.assertEqual(self.run_validate(track(), evidence=self.good_evidence()), [])

    def test_wrong_header_fails(self) -> None:
        self.tracks.write_text("id,title\n")
        self.assertFails(validate(self.tracks, self.dir / "sources.csv", self.evidence), "header")

    def test_duplicate_id_fails(self) -> None:
        self.assertFails(self.run_validate(track(status="pending"), track(status="pending")), "duplicate id")

    def test_unaccepted_licence_fails(self) -> None:
        self.assertFails(self.run_validate(track(status="pending", license="CC-BY-NC-4.0")), "accepted list")

    def test_spoken_word_may_use_nc_nd_on_storytime_only(self) -> None:
        story = track(station="storytime", status="pending", license="CC-BY-NC-ND-4.0", commercial_ok="no")
        self.assertEqual(self.run_validate(story), [])
        self.assertFails(self.run_validate(track(status="pending", license="CC-BY-NC-ND-4.0", commercial_ok="no")), "accepted list")

    def test_non_commercial_licence_needs_commercial_ok_no(self) -> None:
        story = track(station="storytime", status="pending", license="CC-BY-NC-ND-4.0", commercial_ok="yes")
        self.assertFails(self.run_validate(story), "commercial_ok=no")

    def test_rejected_row_may_carry_any_licence(self) -> None:
        self.assertEqual(self.run_validate(track(status="rejected", license="CC-BY-NC-4.0")), [])

    def test_site_licence_passes(self) -> None:
        self.assertEqual(self.run_validate(track(status="pending", license="SITE:chillhop-royalty-free")), [])

    def test_cc_by_needs_attribution(self) -> None:
        self.assertFails(self.run_validate(track(status="pending", attribution="")), "attribution")

    def test_approved_needs_streaming_and_reviewer(self) -> None:
        errors = self.run_validate(track(streaming_ok="no", reviewed_by=""), evidence=self.good_evidence())
        self.assertFails(errors, "streaming_ok=yes")
        self.assertFails(errors, "reviewed_by")

    def test_approved_needs_evidence(self) -> None:
        self.assertFails(self.run_validate(track()), "missing fma-0001.json")

    def test_evidence_hash_must_match(self) -> None:
        self.assertFails(self.run_validate(track(), evidence=self.good_evidence(file_sha256="b" * 64)), "file_sha256")

    def test_bad_id_and_station_fail(self) -> None:
        errors = self.run_validate(track(id="../x", station="Lo Fi", status="pending"))
        self.assertFails(errors, "id must be")
        self.assertFails(errors, "station must be")

    def test_file_name_must_be_a_plain_basename(self) -> None:
        for name in ("fma-0001.mp3\n#EXTINF:-1,x", "lofi/fma-0001.mp3", "fma-0001.mp3\\x", "fma-0001.MP3"):
            with self.subTest(name=name):
                self.assertFails(self.run_validate(track(file_name=name, status="pending")), "file_name must be")

    def test_id_with_trailing_newline_fails(self) -> None:
        self.assertFails(self.run_validate(track(id="fma-0001\n", status="pending")), "id must be")

    def test_sources_without_key_column_fails_cleanly(self) -> None:
        (self.dir / "sources.csv").write_text("name,url\nFMA,https://example.org\n")
        self.assertFails(self.run_validate(track(status="pending")), "key column")

    def test_unknown_source_fails(self) -> None:
        self.assertFails(self.run_validate(track(status="pending", source="nowhere")), "sources.csv")


if __name__ == "__main__":
    unittest.main()
