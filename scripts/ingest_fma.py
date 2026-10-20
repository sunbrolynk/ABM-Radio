"""Brings Free Music Archive tracks into the catalog as pending: reads each track page, refuses any
licence I don't accept, saves the page to the Wayback Machine, downloads the audio into a local
staging folder and writes the tracks.csv row and evidence file.

Usage: python3 scripts/ingest_fma.py <file of track page URLs> <station> <playlists> <staging dir>

One URL per line; blank lines and lines starting with # are skipped, and so is any URL already in
tracks.csv. Tracks go in one at a time with a pause between them, to go easy on FMA and the
Wayback Machine. Nothing here touches the radio server: the staged files are uploaded to its
incoming/ folder afterwards.
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from catalog import COLUMNS, EVIDENCE, TRACKS, read_csv, write_tracks
from hash_files import sha256

UA = {"User-Agent": "Mozilla/5.0 (abm-radio catalog ingest)"}
PAUSE_S = 8
PAGE_HOSTS = {"freemusicarchive.org"}
AUDIO_HOSTS = {"files.freemusicarchive.org"}
MAX_AUDIO_BYTES = 50 * 1024 * 1024
# creativecommons.org path -> (licence id prefix, human name); NC licences are deliberately absent.
LICENCES = {
    "licenses/by/": ("CC-BY", "CC BY"),
    "licenses/by-sa/": ("CC-BY-SA", "CC BY-SA"),
    "licenses/by-nd/": ("CC-BY-ND", "CC BY-ND"),
    "publicdomain/zero/": ("CC0", "CC0"),
}


def check_url(url: str, hosts: set[str]) -> None:
    """Only https, and only hosts I've seen FMA use, so a changed page can't point anywhere else."""
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in hosts:
        raise ValueError(f"refusing {url!r}: not https on {sorted(hosts)}")


def fetch(url: str, hosts: set[str], limit: int = MAX_AUDIO_BYTES) -> tuple[bytes, str]:
    """Fetches url, refusing redirects off the allowed hosts and bodies over limit. Returns (body, content type)."""
    check_url(url, hosts)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        check_url(r.geturl(), hosts)
        body = b""
        while chunk := r.read(1024 * 1024):
            body += chunk
            if len(body) > limit:
                raise ValueError(f"{url} is over {limit} bytes")
        return body, r.headers.get_content_type()


def parse_track_page(page: str, url: str) -> dict[str, str]:
    """Pulls the track's own data out of an FMA track page. Raises ValueError if anything is off."""
    info = None
    for raw in re.findall(r"data-track-info='([^']*)'", page):
        data = json.loads(html.unescape(raw))
        if data.get("url", "").rstrip("/") == url.rstrip("/"):
            info = data
            break
    if info is None:
        raise ValueError("no track data for this URL on the page")
    links = {m.group(1).rstrip("/") for m in re.finditer(r'rel="license"[^>]*href="([^"]+)"', page)}
    if len(links) != 1:
        raise ValueError(f"expected exactly one licence link on the page, found {sorted(links) or 'none'}")
    link = re.search(r'rel="license"[^>]*href="https?://creativecommons\.org/([^"]+?)/?"', page)
    if not link:
        raise ValueError(f"licence link {links.pop()!r} isn't a Creative Commons one")
    path = link.group(1)
    match = next((v for k, v in LICENCES.items() if path.startswith(k)), None)
    version = re.search(r"/(\d\.\d)$", path)
    if not match or not version:
        raise ValueError(f"licence {path!r} is not one I accept")
    prefix, name = match
    licence = "CC0-1.0" if prefix == "CC0" else f"{prefix}-{version.group(1)}"
    deed = f"https://creativecommons.org/{path}/"
    block = page[page.find(">", link.end()) + 1 : page.find("</div>", link.end())]
    quote = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", block))).strip()
    quote = re.sub(r"\s+([.,])", r"\1", quote)
    title, artist = info["title"].strip(), info["artistName"].strip()
    album = "" if info.get("albumTitle", "-") in ("-", "") else info["albumTitle"].strip()
    credit = name if prefix == "CC0" else f"{name} {version.group(1)}"
    return {
        "title": title,
        "artist": artist,
        "album": album,
        "license": licence,
        "license_url": deed,
        "attribution": f'"{title}" by {artist}, {credit}',
        "quote": quote,
        "file_url": info["fileUrl"],
    }


def next_id(rows: list[dict[str, str]], prefix: str = "fma") -> str:
    used = [int(r["id"].rsplit("-", 1)[1]) for r in rows if r["id"].startswith(prefix + "-")]
    return f"{prefix}-{max(used, default=0) + 1:04d}"


def wayback(url: str) -> str:
    """Asks the Wayback Machine to save the page and returns the snapshot URL, or '' if it failed."""
    try:
        with urllib.request.urlopen(urllib.request.Request("https://web.archive.org/save/" + url, headers=UA), timeout=180) as r:
            final = r.geturl()
            return final if "/web/" in final else ""
    except OSError:
        return ""


def ingest(url: str, station: str, playlists: str, staging: Path) -> str:
    _, rows = read_csv(TRACKS)
    if any(r["source_url"].rstrip("/") == url.rstrip("/") for r in rows):
        return f"skip (already catalogued): {url}"
    page, _ = fetch(url, PAGE_HOSTS, limit=5 * 1024 * 1024)
    t = parse_track_page(page.decode("utf-8", "replace"), url)
    audio, kind = fetch(t["file_url"], AUDIO_HOSTS)
    if kind != "audio/mpeg":  # MP3 only: it's what FMA serves and what the file name says
        raise ValueError(f"audio is {kind!r}, not audio/mpeg")
    tid = next_id(rows)
    file_name = f"{tid}.mp3"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / file_name).write_bytes(audio)
    digest = sha256(staging / file_name)
    archived = wayback(url)
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        id=tid, title=t["title"], artist=t["artist"], album=t["album"], source="fma", source_url=url,
        license=t["license"], license_url=t["license_url"], attribution=t["attribution"],
        commercial_ok="yes", streaming_ok="yes", downloaded_at=date.today().isoformat(),
        file_name=file_name, sha256=digest, station=station, playlists=playlists, status="pending",
    )  # fmt: skip
    write_tracks([*rows, row])
    evidence = {
        "id": tid,
        "source_url": url,
        "license": t["license"],
        "license_text_quote": t["quote"],
        "archived_url": archived,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_sha256": digest,
    }
    (EVIDENCE / f"{tid}.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    note = "" if archived else " (Wayback save failed; retry before approving)"
    return f"{tid}: {t['artist']} - {t['title']} [{t['license']}]{note}"


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: ingest_fma.py <url file> <station> <playlists> <staging dir>")
    urls = [u.strip() for u in Path(sys.argv[1]).read_text().splitlines() if u.strip() and not u.startswith("#")]
    failed = 0
    for i, u in enumerate(urls):
        try:
            print(ingest(u, sys.argv[2], sys.argv[3], Path(sys.argv[4])), flush=True)
        except (ValueError, OSError, KeyError, json.JSONDecodeError) as e:
            failed += 1
            print(f"REFUSED {u}: {e}", file=sys.stderr, flush=True)
        if i < len(urls) - 1:
            time.sleep(PAUSE_S)
    sys.exit(1 if failed else 0)
