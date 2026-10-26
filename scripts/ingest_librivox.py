"""Brings a LibriVox book into the catalog as pending story blocks: whole sections joined back to
back into blocks of about a target length, never cutting a section, each with a catalog row and
licence proof. Writes the blocks to a staging folder for upload to the station.

Usage: python3 scripts/ingest_librivox.py <book id> <station> <playlist> <minutes> <staging dir>

The book id is the number in the book's LibriVox feed (librivox.org/rss/<id>). Downloaded sections
are cached in <staging dir>/cache/<id>/, so building the same book again fetches nothing and gives
byte-identical blocks. Joining needs no re-encoding: one recording's sections share their format.
"""

# Python Imports
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

# Local Imports
from catalog import COLUMNS, EVIDENCE, TRACKS, read_csv, write_tracks
from hash_files import sha256
from ingest_fma import wayback
from tag_mp3 import tag

UA = {"User-Agent": "abm-radio catalog (radio.audiobookmanager.com)"}
PD_URL = "https://librivox.org/pages/public-domain/"
PD_LINE = "LibriVox recordings are Public Domain in the USA."  # on every book page
MAX_SECTION_BYTES = 300 * 1024 * 1024


def allowed(url: str) -> bool:
    host = urllib.parse.urlsplit(url).hostname or ""
    return url.startswith("https://") and (host in ("librivox.org", "archive.org") or host.endswith(".archive.org"))


def get(url: str, limit: int) -> bytes:
    if not allowed(url):
        raise ValueError(f"not an allowed host: {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        if not allowed(r.geturl()):
            raise ValueError(f"redirected off the allowed hosts: {r.geturl()}")
        body = r.read(limit + 1)
    if len(body) > limit:
        raise ValueError(f"over {limit} bytes: {url}")
    return body


def frame_len(h: bytes) -> int:
    """Length of the MPEG Layer III frame whose 4-byte header is h, or 0 if h isn't one."""
    if len(h) < 4 or h[0] != 0xFF or h[1] & 0xE0 != 0xE0:
        return 0
    version, layer = (h[1] >> 3) & 3, (h[1] >> 1) & 3
    if layer != 1 or version == 1:
        return 0
    mpeg1 = version == 3
    rates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320] if mpeg1 else [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
    srs = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}[version]
    bi, si = h[2] >> 4, (h[2] >> 2) & 3
    if bi in (0, 15) or si == 3:
        return 0
    return (144 if mpeg1 else 72) * rates[bi] * 1000 // srs[si] + ((h[2] >> 1) & 1)


def audio_frames(data: bytes) -> bytes:
    """The raw audio of an MP3: no ID3 tags, and no Xing/Info header frame (it would give the
    joined block the first section's length)."""
    if data[:3] == b"ID3":
        data = data[10 + ((data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]) :]
    if data[-128:-125] == b"TAG":
        data = data[:-128]
    start = next((i for i in range(min(len(data), 65536)) if frame_len(data[i : i + 4])), None)
    if start is None:
        raise ValueError("no MP3 frames found")
    data = data[start:]
    n = frame_len(data[:4])
    if b"Xing" in data[:n] or b"Info" in data[:n]:
        data = data[n:]
    return data


def plan(sections: list[dict], target_s: int) -> list[list[dict]]:
    """Whole sections back to back; a block closes when the next section would take it more than a
    quarter past the target, so a section longer than that is a block of its own."""
    blocks, cur, total = [], [], 0
    for s in sections:
        t = int(s["playtime"])
        if cur and total + t > target_s * 1.25:
            blocks.append(cur)
            cur, total = [], 0
        cur.append(s)
        total += t
    if cur:
        blocks.append(cur)
    return blocks


def readers(block: list[dict]) -> str:
    return ", ".join(sorted({r["display_name"] for s in block for r in s.get("readers", [])}))


def ingest(book_id: str, station: str, playlist: str, minutes: int, staging: Path, tracks: Path = TRACKS, evidence: Path = EVIDENCE) -> list[str]:
    q = urllib.parse.urlencode({"id": book_id, "format": "json", "extended": 1})
    book = json.loads(get(f"https://librivox.org/api/feed/audiobooks?{q}", 5_000_000))["books"][0]
    page_url = book["url_librivox"]
    page = get(page_url, 5_000_000).decode("utf-8", "replace")
    if PD_LINE not in re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)):
        raise ValueError(f"the book page doesn't carry the public-domain line: {page_url}")
    author = ", ".join(f'{a["first_name"]} {a["last_name"]}'.strip() for a in book["authors"])
    blocks = plan(sorted(book["sections"], key=lambda s: int(s["section_number"])), minutes * 60)
    archived = wayback(page_url)
    cache = staging / "cache" / book_id
    cache.mkdir(parents=True, exist_ok=True)
    _, rows = read_csv(tracks)
    known = {r["id"]: r for r in rows if r["id"].startswith(f"lv-{book_id}-b")}
    if known and len(known) != len(blocks):
        raise ValueError(f"lv-{book_id} is catalogued as {len(known)} blocks, this split makes {len(blocks)}: retire the old rows first")
    new: dict[str, dict] = {}
    done = []
    for n, block in enumerate(blocks, 1):
        tid = f"lv-{book_id}-b{n:02d}"
        audio = b""
        for s in block:
            f = cache / f'{int(s["section_number"]):03d}.mp3'
            if not f.is_file():
                f.write_bytes(get(s["listen_url"], MAX_SECTION_BYTES))
            audio += audio_frames(f.read_bytes())
        path = staging / f"{tid}.mp3"
        tmp = path.with_suffix(".building")
        tmp.write_bytes(audio)
        titles = "; ".join(s["title"] for s in block)
        credit = f"Read by {readers(block)} for LibriVox"
        tag(tmp, f'{book["title"]}, part {n} of {len(blocks)}: {titles}', author, book["title"], f"{credit}. Public domain. {page_url}",
            {"genres": ["Audiobook"], "licence": "Public Domain", "licence_url": PD_URL, "source_url": page_url})
        digest = sha256(tmp)
        if tid in known and known[tid]["sha256"] != digest and known[tid]["status"] != "pending":
            tmp.unlink()  # reviewed audio never changes under the same id
            raise ValueError(f"{tid} would change but is already {known[tid]['status']}: retire it first")
        tmp.replace(path)
        ev = {
            "id": tid, "source_url": page_url, "license": "PD", "license_url": PD_URL,
            "license_text_quote": PD_LINE, "archived_url": archived,
            "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "file_sha256": digest,
            "page_metadata": {"book_id": book_id, "archive_org": book.get("url_iarchive", ""), "sections": [s["section_number"] for s in block]},
        }  # fmt: skip
        (evidence / f"{tid}.json").write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if tid not in known or known[tid]["sha256"] != digest:
            row = dict.fromkeys(COLUMNS, "")
            row.update(
                id=tid, title=f'{book["title"]}, part {n} of {len(blocks)}', artist=author, album=book["title"], source="librivox",
                source_url=page_url, license="PD", license_url=PD_URL, attribution=f'"{book["title"]}" by {author}, {credit}',
                commercial_ok="yes", streaming_ok="yes", downloaded_at=date.today().isoformat(), file_name=path.name, sha256=digest,
                duration_s=str(sum(int(s["playtime"]) for s in block)), station=station, playlists=playlist, status="pending",
                notes=f"Sections: {titles}",
            )  # fmt: skip
            new[tid] = row
        done.append(tid)
    # Re-read just before saving: the downloads take a while, and approvals may land meanwhile.
    _, rows = read_csv(tracks)
    reviewed = [r["id"] for r in rows if r["id"] in new and r["status"] != "pending"]
    if reviewed:
        raise ValueError(f"reviewed while this ran, so left as they were: {', '.join(reviewed)}")
    rows = [new.pop(r["id"], r) for r in rows] + list(new.values())
    write_tracks(rows, tracks)
    return done


if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit("usage: ingest_librivox.py <book id> <station> <playlist> <minutes> <staging dir>")
    ids = ingest(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), Path(sys.argv[5]))
    print(f"lv-{sys.argv[1]}: {len(ids)} blocks", flush=True)
