"""Hashes the audio files on the server and writes the sha256 into tracks.csv.

Usage: python3 scripts/hash_files.py /path/to/station/media

Finds each row's file_name anywhere under the media folder. It also fills an evidence file's
empty file_sha256. A hash that changed on an approved track is reported and left alone: that
file is no longer the one I reviewed.
"""

import hashlib
import json
import sys
from pathlib import Path

from catalog import COLUMNS, EVIDENCE, TRACKS, read_csv, write_tracks


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def hash_files(media: Path, tracks: Path = TRACKS, evidence: Path = EVIDENCE) -> list[str]:
    header, rows = read_csv(tracks)
    if header != COLUMNS:
        return ["tracks.csv header is wrong; run validate.py first"]
    wanted = {r["file_name"] for r in rows if r["file_name"] and r["status"] != "rejected"}
    found: dict[str, set[str]] = {}
    for p in media.rglob("*"):
        if p.name in wanted and p.is_file():
            found.setdefault(p.name, set()).add(sha256(p))
    problems: list[str] = []
    for r in rows:
        name = r["file_name"]
        if name not in wanted:
            continue
        hashes = found.get(name)
        if not hashes:
            problems.append(f"{r['id']}: {name} not found under {media}")
            continue
        if len(hashes) > 1:
            problems.append(f"{r['id']}: copies of {name} differ")
            continue
        digest = hashes.pop()
        if r["sha256"] and r["sha256"] != digest and r["status"] == "approved":
            problems.append(f"{r['id']}: file changed since it was approved; left the old hash, re-review it")
            continue
        r["sha256"] = digest
        ev_path = evidence / f"{r['id']}.json"
        if ev_path.is_file():
            ev = json.loads(ev_path.read_text(encoding="utf-8"))
            if not ev.get("file_sha256"):
                ev["file_sha256"] = digest
                ev_path.write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    write_tracks(rows, tracks)
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit("usage: hash_files.py <media folder>")
    problems = hash_files(Path(sys.argv[1]))
    for p in problems:
        print(p, file=sys.stderr)
    sys.exit(1 if problems else 0)
