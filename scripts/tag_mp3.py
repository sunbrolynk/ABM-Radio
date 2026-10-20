"""Writes the catalog's title, artist, album and credit into each pending MP3's ID3 tag, then
updates its sha256 in tracks.csv and the evidence, since the file on air is the tagged one.

Usage: python3 scripts/tag_mp3.py <staging dir>

Keeps every other frame already in the tag (cover art and the like). Approved rows are never
touched: their files are the ones I reviewed.
"""

import json
import struct
import sys
from pathlib import Path

from catalog import EVIDENCE, TRACKS, read_csv, write_tracks
from hash_files import sha256

MINE = {b"TIT2", b"TPE1", b"TALB", b"COMM"}


def _syncsafe(n: int) -> bytes:
    return bytes((n >> s) & 0x7F for s in (21, 14, 7, 0))


def _unsyncsafe(b: bytes) -> int:
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _utf16(s: str) -> bytes:
    return s.encode("utf-16")  # with BOM, valid in ID3 v2.3 and v2.4


def _frame(fid: bytes, data: bytes, major: int) -> bytes:
    size = _syncsafe(len(data)) if major == 4 else struct.pack(">I", len(data))
    return fid + size + b"\0\0" + data


def _split(data: bytes) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Returns (major version, other frames as (id, raw bytes), audio) for a file's leading ID3v2 tag."""
    if data[:3] != b"ID3":
        return 3, [], data
    major, flags = data[3], data[5]
    end = 10 + _unsyncsafe(data[6:10]) + (10 if flags & 0x10 else 0)
    if major not in (3, 4) or flags & 0xC0:  # v2.2, unsynchronised or extended headers: start a fresh tag
        return 3, [], data[end:]
    frames, pos, limit = [], 10, 10 + _unsyncsafe(data[6:10])
    while pos + 10 <= limit and data[pos : pos + 4].strip(b"\0"):
        size_bytes = data[pos + 4 : pos + 8]
        size = _unsyncsafe(size_bytes) if major == 4 else struct.unpack(">I", size_bytes)[0]
        frames.append((data[pos : pos + 4], data[pos : pos + 10 + size]))
        pos += 10 + size
    return major, frames, data[end:]


def tag(path: Path, title: str, artist: str, album: str, comment: str) -> None:
    data = path.read_bytes()
    major, frames, audio = _split(data)
    body = b"".join(raw for fid, raw in frames if fid not in MINE)
    body += _frame(b"TIT2", b"\x01" + _utf16(title), major)
    body += _frame(b"TPE1", b"\x01" + _utf16(artist), major)
    if album:
        body += _frame(b"TALB", b"\x01" + _utf16(album), major)
    body += _frame(b"COMM", b"\x01eng" + _utf16("") + b"\0\0" + _utf16(comment), major)
    header = b"ID3" + bytes([major, 0, 0]) + _syncsafe(len(body))
    tmp = path.with_suffix(".tagging")
    tmp.write_bytes(header + body + audio)
    tmp.replace(path)


def read_tags(path: Path) -> dict[str, str]:
    """The text frames this script writes, decoded; for checking a tagged file."""
    major, frames, _ = _split(path.read_bytes())
    out = {}
    for fid, raw in frames:
        if fid in (b"TIT2", b"TPE1", b"TALB"):
            out[fid.decode()] = raw[11:].decode("utf-16")
    return out


def tag_pending(staging: Path, tracks: Path = TRACKS, evidence: Path = EVIDENCE) -> list[str]:
    _, rows = read_csv(tracks)
    done = []
    for r in rows:
        f = staging / r["file_name"]
        if r["status"] != "pending" or not f.is_file():
            continue
        tag(f, r["title"], r["artist"], r["album"], f"{r['attribution']}. {r['source_url']}")
        r["sha256"] = sha256(f)
        ev_path = evidence / f"{r['id']}.json"
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        ev["file_sha256"] = r["sha256"]
        ev_path.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        done.append(r["id"])
    write_tracks(rows, tracks)
    return done


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit("usage: tag_mp3.py <staging dir>")
    done = tag_pending(Path(sys.argv[1]))
    print(f"tagged {len(done)} pending files")
