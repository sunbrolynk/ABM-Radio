"""Marks pending tracks approved and prints the SFTP commands that move them on air.

Usage: python3 scripts/approve.py [--kid-safe] <reviewer> <folder> <id> [<id> ...]

Sets status=approved and reviewed_by for each id (and kid_safe=yes with --kid-safe, which says I
checked them for a kids station; Lil' Beats tracks can't be approved without it), then runs validate.py: if anything fails, the
catalog is left untouched. The printed `rename incoming/<file> <folder>/<file>` lines go to
sftp's batch mode (`sftp -b -`) to move the files into the playlist folder.
"""

# Python Imports
import sys

# Local Imports
from catalog import EVIDENCE, SOURCES, TRACKS, read_csv, write_tracks
from validate import validate


def approve(reviewer: str, ids: list[str], tracks=TRACKS, sources=SOURCES, evidence=EVIDENCE, kid_safe: bool = False) -> list[str]:
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
        if kid_safe:
            by_id[i]["kid_safe"] = "yes"
    original = tracks.read_bytes()
    write_tracks(rows, tracks)
    if problems := validate(tracks, sources, evidence):
        tracks.write_bytes(original)  # put it back: an approval that doesn't validate never sticks
        hint = " (an empty archived_url means the Wayback save failed: save the page again first)"
        raise ValueError("validation failed, nothing approved" + (hint if any("archived_url" in p for p in problems) else "") + ":\n" + "\n".join(problems))
    return [by_id[i]["file_name"] for i in ids]


if __name__ == "__main__":
    args = sys.argv[1:]
    kid_safe = args[:1] == ["--kid-safe"]
    args = args[1:] if kid_safe else args
    if len(args) < 3:
        sys.exit("usage: approve.py [--kid-safe] <reviewer> <folder> <id> [<id> ...]")
    try:
        files = approve(args[0], args[2:], kid_safe=kid_safe)
    except ValueError as e:
        sys.exit(str(e))
    for f in files:
        print(f"rename incoming/{f} {args[1]}/{f}")
