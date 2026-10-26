"""Writes out/credits.json for the website: every approved track, sorted by station, artist, then title.

Refuses to run on a catalog that fails validate.py, so nothing unchecked reaches the credits.
"""

# Python Imports
import json
import sys
from pathlib import Path

# Local Imports
from catalog import OUT, TRACKS, approved, read_csv
from validate import validate

FIELDS = ["id", "station", "title", "artist", "album", "license", "license_url", "source_url", "attribution"]


def export_credits(tracks: Path = TRACKS, out: Path = OUT) -> Path:
    rows = sorted(approved(read_csv(tracks)[1]), key=lambda r: (r["station"], r["artist"].casefold(), r["title"].casefold(), r["id"]))
    out.mkdir(exist_ok=True)
    path = out / "credits.json"
    path.write_text(json.dumps([{k: r[k] for k in FIELDS} for r in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    if problems := validate():
        sys.exit("catalog fails validate.py; fix that first:\n" + "\n".join(problems))
    print(export_credits())
