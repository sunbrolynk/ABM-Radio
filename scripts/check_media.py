"""Checks that everything on air is approved: every audio file under the media folder, except
in incoming/, must match an approved row by file name and sha256.

Usage: python3 scripts/check_media.py /path/to/station/media

New files wait in incoming/ (a folder linked to no playlist) until their row is approved, then
move into a playlist folder. Exits 1 on any file that shouldn't be playing.
"""

# Python Imports
import sys
from pathlib import Path

# Local Imports
from catalog import TRACKS, approved, read_csv
from hash_files import sha256

AUDIO = {".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wav"}


def check_media(media: Path, tracks: Path = TRACKS) -> list[str]:
    hashes = {r["file_name"]: r["sha256"] for r in approved(read_csv(tracks)[1])}
    problems = []
    for p in sorted(media.rglob("*")):
        rel = p.relative_to(media)
        if rel.parts[0] == "incoming" or p.suffix.lower() not in AUDIO or not p.is_file():
            continue
        if p.is_symlink():
            problems.append(f"{rel}: a symlink, not a real file")
        elif p.name not in hashes:
            problems.append(f"{rel}: no approved row in tracks.csv")
        elif sha256(p) != hashes[p.name]:
            problems.append(f"{rel}: sha256 differs from the approved file")
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit("usage: check_media.py <media folder>")
    problems = check_media(Path(sys.argv[1]))
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        sys.exit(1)
    print("media OK: everything outside incoming/ is approved")
