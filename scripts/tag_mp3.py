"""Writes the catalog's title, artist, album and credit, plus genre, release date, cover art,
licence and source link, into each pending MP3's ID3 tag. Then it updates the file's sha256 in
tracks.csv and the evidence, since the file on air is the tagged one.

Usage: python3 scripts/tag_mp3.py <staging dir>

Keeps every other frame already in the tag, and never replaces cover art the artist embedded.
The extras come from the evidence file's page_metadata, and the cover from <id>.art in staging.
Approved rows are never touched: their files are the ones I reviewed.
"""

import json
import re
import struct
import sys
from pathlib import Path

from catalog import EVIDENCE, TRACKS, read_csv, write_tracks
from hash_files import sha256

MINE = {b"TIT2", b"TPE1", b"TALB", b"COMM", b"TCON", b"TYER", b"TDRC", b"TCOP", b"WCOP", b"WOAS"}


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


def image_mime(data: bytes) -> str:
    """The real type of an image from its first bytes; '' for anything but JPEG or PNG (WebP included)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return ""


def apic_image(raw: bytes) -> bytes:
    """The picture bytes inside a raw APIC frame (header included)."""
    body = raw[10:]
    enc, rest = body[0], body[1:]
    rest = rest[rest.index(b"\0") + 1 :]  # MIME type
    rest = rest[1:]  # picture type
    if enc in (1, 2):  # UTF-16 description ends in a two-byte null on an even boundary
        i = 0
        while rest[i : i + 2] != b"\0\0":
            i += 2
        return rest[i + 2 :]
    return rest[rest.index(b"\0") + 1 :]


def tag(path: Path, title: str, artist: str, album: str, comment: str, extra: dict | None = None) -> None:
    """extra may hold genres (list), released (YYYY-MM-DD), licence (e.g. "CC BY 4.0"),
    licence_url, source_url, art (bytes) and art_mime."""
    extra = extra or {}
    data = path.read_bytes()
    major, frames, audio = _split(data)
    # A cover that isn't a real JPEG or PNG (an earlier WebP mistake) is dropped so it can be replaced.
    frames = [(fid, raw) for fid, raw in frames if fid != b"APIC" or image_mime(apic_image(raw))]
    kept = b"".join(raw for fid, raw in frames if fid not in MINE)
    body = b""
    text = lambda fid, value: _frame(fid, b"\x01" + _utf16(value), major)  # noqa: E731
    url = lambda fid, value: _frame(fid, value.encode("latin-1"), major)  # noqa: E731
    body += text(b"TIT2", title) + text(b"TPE1", artist)
    if album:
        body += text(b"TALB", album)
    body += _frame(b"COMM", b"\x01eng" + _utf16("") + b"\0\0" + _utf16(comment), major)
    if extra.get("genres"):
        body += text(b"TCON", ", ".join(extra["genres"]))
    released = extra.get("released", "")
    if released:
        body += text(b"TDRC", released) if major == 4 else text(b"TYER", released[:4])
    if extra.get("licence"):
        body += text(b"TCOP", f"{released[:4]} {artist}. {extra['licence']}".strip())
    if extra.get("licence_url"):
        body += url(b"WCOP", extra["licence_url"])
    if extra.get("source_url"):
        body += url(b"WOAS", extra["source_url"])
    body += kept  # mine first, then the file's own, so re-tagging gives identical bytes
    if extra.get("art") and image_mime(extra["art"]) and not any(fid == b"APIC" for fid, _ in frames):
        mime = image_mime(extra["art"]).encode("latin-1")
        body += _frame(b"APIC", b"\x00" + mime + b"\x00\x03\x00" + extra["art"], major)
    header = b"ID3" + bytes([major, 0, 0]) + _syncsafe(len(body))
    tmp = path.with_suffix(".tagging")
    tmp.write_bytes(header + body + audio)
    tmp.replace(path)


def read_tags(path: Path) -> dict[str, str]:
    """The text frames this script writes, decoded; for checking a tagged file."""
    major, frames, _ = _split(path.read_bytes())
    out = {}
    for fid, raw in frames:
        if fid in (b"TIT2", b"TPE1", b"TALB", b"TCON", b"TYER", b"TDRC", b"TCOP"):
            out[fid.decode()] = raw[11:].decode("utf-16")
        elif fid in (b"WCOP", b"WOAS"):
            out[fid.decode()] = raw[10:].decode("latin-1")
        elif fid == b"APIC":
            out["APIC"] = image_mime(apic_image(raw)) or "invalid"
    return out


def licence_name(licence_id: str) -> str:
    """"CC-BY-SA-4.0" -> "CC BY-SA 4.0", "CC0-1.0" -> "CC0 1.0", "PD" -> "Public Domain"."""
    if licence_id == "PD":
        return "Public Domain"
    m = re.fullmatch(r"(CC0|CC-[A-Z-]+?)-(\d\.\d)", licence_id)
    return f"{m.group(1).replace('CC-', 'CC ', 1)} {m.group(2)}" if m else licence_id


def extras(r: dict[str, str], ev: dict, staging: Path) -> dict:
    meta = ev.get("page_metadata", {})
    extra = {
        "genres": meta.get("genres", []),
        "released": meta.get("released", ""),
        "licence": licence_name(r["license"]),
        "licence_url": r["license_url"],
        "source_url": r["source_url"],
    }
    art = staging / f"{r['id']}.art"
    if art.is_file() and image_mime(art.read_bytes()):
        extra["art"] = art.read_bytes()
    return extra


def tag_pending(staging: Path, tracks: Path = TRACKS, evidence: Path = EVIDENCE) -> list[str]:
    _, rows = read_csv(tracks)
    hashes = {}
    for r in rows:
        f = staging / r["file_name"]
        if r["status"] != "pending" or not f.is_file():
            continue
        ev_path = evidence / f"{r['id']}.json"
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        tag(f, r["title"], r["artist"], r["album"], f"{r['attribution']}. {r['source_url']}", extras(r, ev, staging))
        hashes[r["id"]] = ev["file_sha256"] = sha256(f)
        ev_path.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Re-read before writing, so a row an ingest added meanwhile isn't lost.
    _, rows = read_csv(tracks)
    for r in rows:
        if r["id"] in hashes and r["status"] == "pending":
            r["sha256"] = hashes[r["id"]]
    write_tracks(rows, tracks)
    return list(hashes)


def fix_approved_art(staging: Path, tracks: Path = TRACKS, evidence: Path = EVIDENCE) -> list[str]:
    """Replaces a broken embedded cover in approved files, or adds one where it's missing and a real
    JPEG or PNG is staged. The audio must come out byte-identical, or the file is left as it was:
    only the picture changes, never what was reviewed."""
    _, rows = read_csv(tracks)
    fixed = {}
    for r in rows:
        f = staging / r["file_name"]
        if r["status"] != "approved" or not f.is_file():
            continue
        before = f.read_bytes()
        _, frames, audio = _split(before)
        broken = any(fid == b"APIC" and not image_mime(apic_image(raw)) for fid, raw in frames)
        art = staging / f"{r['id']}.art"
        missing = not any(fid == b"APIC" for fid, _ in frames) and art.is_file() and image_mime(art.read_bytes())
        if not (broken or missing):
            continue  # a good cover already, or nothing better to add
        ev_path = evidence / f"{r['id']}.json"
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        tag(f, r["title"], r["artist"], r["album"], f"{r['attribution']}. {r['source_url']}", extras(r, ev, staging))
        if _split(f.read_bytes())[2] != audio:
            f.write_bytes(before)
            raise ValueError(f"{r['id']}: audio changed while fixing the cover; file restored")
        fixed[r["id"]] = ev["file_sha256"] = sha256(f)
        ev_path.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _, rows = read_csv(tracks)
    for r in rows:
        if r["id"] in fixed:
            r["sha256"] = fixed[r["id"]]
            note = "Cover art replaced 2026-10-20 (the first was a mislabelled WebP); audio unchanged."
            if note not in r["notes"]:
                r["notes"] = f"{r['notes']} {note}".strip()
    write_tracks(rows, tracks)
    return list(fixed)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fix-approved-art":
        print(f"fixed covers on {len(fix_approved_art(Path(sys.argv[2])))} approved files")
        sys.exit(0)
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit("usage: tag_mp3.py <staging dir>  |  tag_mp3.py --fix-approved-art <staging dir>")
    done = tag_pending(Path(sys.argv[1]))
    print(f"tagged {len(done)} pending files")
