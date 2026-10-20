"""Marks pending tracks approved and prints the SFTP commands that move them on air.

Usage: python3 scripts/approve.py <reviewer> <folder> <id> [<id> ...]

Sets status=approved and reviewed_by for each id, then runs validate.py: if anything fails, the
catalog is left untouched. The printed `rename incoming/<file> <folder>/<file>` lines go to
sftp's batch mode (`sftp -b -`) to move the files into the playlist folder.
"""

import sys

from catalog import EVIDENCE, SOURCES, TRACKS, read_csv, write_tracks
from validate import validate


def approve(reviewer: str, ids: list[str], tracks=TRACKS, sources=SOURCES, evidence=EVIDENCE) -> list[str]:
    _, rows = read_csv(tracks)
    by_id = {r["id"]: r for r in rows}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise ValueError(f"not in tracks.csv: {', '.join(missing)}")
    not_pending = [i for i in ids if by_id[i]["status"] != "pending"]
    if not_pending:
        raise ValueError(f"not pending: {', '.join(not_pending)}")
    for i in ids:
        by_id[i].update(status="approved", reviewed_by=reviewer)
    original = tracks.read_bytes()
    write_tracks(rows, tracks)
    if problems := validate(tracks, sources, evidence):
        tracks.write_bytes(original)  # put it back: an approval that doesn't validate never sticks
        hint = " (an empty archived_url means the Wayback save failed: save the page again first)"
        raise ValueError("validation failed, nothing approved" + (hint if any("archived_url" in p for p in problems) else "") + ":\n" + "\n".join(problems))
    return [by_id[i]["file_name"] for i in ids]


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit("usage: approve.py <reviewer> <folder> <id> [<id> ...]")
    try:
        files = approve(sys.argv[1], sys.argv[3:])
    except ValueError as e:
        sys.exit(str(e))
    for f in files:
        print(f"rename incoming/{f} {sys.argv[2]}/{f}")
