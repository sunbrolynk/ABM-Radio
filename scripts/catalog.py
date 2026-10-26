"""Shared bits for the catalog scripts: paths, columns, and reading/writing tracks.csv."""

# Python Imports
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKS = ROOT / "catalog" / "tracks.csv"
SOURCES = ROOT / "catalog" / "sources.csv"
EVIDENCE = ROOT / "evidence"
OUT = ROOT / "out"

COLUMNS = [
    "id", "title", "artist", "album", "source", "source_url", "license", "license_url",
    "attribution", "commercial_ok", "streaming_ok", "kid_safe", "downloaded_at", "file_name", "sha256",
    "duration_s", "station", "playlists", "status", "reviewed_by", "notes",
]  # fmt: skip


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_tracks(rows: list[dict[str, str]], path: Path = TRACKS) -> None:
    # Write beside it and swap, so a failed write never leaves a half-written catalog.
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def approved(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r["status"] == "approved"]
