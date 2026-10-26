"""Writes out/<station>/<playlist>.m3u for each playlist named in tracks.csv, approved tracks only.

Refuses to run on a catalog that fails validate.py, so nothing unchecked goes on air.
"""

# Python Imports
import sys
from pathlib import Path

# Local Imports
from catalog import OUT, TRACKS, approved, read_csv
from validate import validate


def export_playlists(tracks: Path = TRACKS, out: Path = OUT) -> list[Path]:
    playlists: dict[tuple[str, str], list[str]] = {}
    for r in approved(read_csv(tracks)[1]):
        for name in filter(None, r["playlists"].split(";")):
            playlists.setdefault((r["station"], name), []).append(r["file_name"])
    paths = []
    for (station, name), files in sorted(playlists.items()):
        (out / station).mkdir(parents=True, exist_ok=True)
        path = out / station / f"{name}.m3u"
        path.write_text("#EXTM3U\n" + "".join(f"{f}\n" for f in files), encoding="utf-8")
        paths.append(path)
    return paths


if __name__ == "__main__":
    if problems := validate():
        sys.exit("catalog fails validate.py; fix that first:\n" + "\n".join(problems))
    for p in export_playlists():
        print(p)
