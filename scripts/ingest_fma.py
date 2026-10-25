"""Brings Free Music Archive tracks into the catalog as pending: reads each track page, refuses any
licence I don't accept, saves the page to the Wayback Machine, downloads the audio into a local
staging folder and writes the tracks.csv row and evidence file.

Usage: python3 scripts/ingest_fma.py <file of track page URLs> <station> <playlists> <staging dir>
       python3 scripts/ingest_fma.py --enrich <staging dir>

--enrich fetches genre, release date and cover art for pending FMA tracks that don't have them
yet (or whose cover isn't a real JPEG or PNG), then re-tags every pending file.

One URL per line; blank lines and lines starting with # are skipped, and so is any URL already in
tracks.csv. Tracks go in one at a time with a pause between them, to go easy on FMA and the
Wayback Machine. Nothing here touches the radio server: the staged files are uploaded to its
incoming/ folder afterwards.
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from catalog import COLUMNS, EVIDENCE, TRACKS, read_csv, write_tracks
from hash_files import sha256
from tag_mp3 import extras, image_mime, tag, tag_pending

UA = {"User-Agent": "Mozilla/5.0 (abm-radio catalog ingest)"}
PAUSE_S = 8
PAGE_HOSTS = {"freemusicarchive.org"}
AUDIO_HOSTS = {"files.freemusicarchive.org"}
MAX_AUDIO_BYTES = 50 * 1024 * 1024
MAX_ART_BYTES = 8 * 1024 * 1024
FMA = re.escape("https://freemusicarchive.org")
# creativecommons.org path -> (licence id prefix, human name); NC licences are deliberately absent.
LICENCES = {
    "licenses/by/": ("CC-BY", "CC BY"),
    "licenses/by-sa/": ("CC-BY-SA", "CC BY-SA"),
    "licenses/by-nd/": ("CC-BY-ND", "CC BY-ND"),
    "publicdomain/zero/": ("CC0", "CC0"),
    # The Public Domain Mark, and the old dedication it replaced: no version needed, both are PD.
    "publicdomain/mark/": ("PD", "Public Domain"),
    "licenses/publicdomain": ("PD", "Public Domain"),
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
    if not match or not (version or match[0] == "PD"):
        raise ValueError(f"licence {path!r} is not one I accept")
    prefix, name = match
    licence = {"CC0": "CC0-1.0", "PD": "PD"}.get(prefix) or f"{prefix}-{version.group(1)}"
    deed = f"https://creativecommons.org/{path}/"
    block = page[page.find(">", link.end()) + 1 : page.find("</div>", link.end())]
    quote = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", block))).strip()
    quote = re.sub(r"\s+([.,])", r"\1", quote)
    title, artist = info["title"].strip(), info["artistName"].strip()
    album = "" if info.get("albumTitle", "-") in ("-", "") else info["albumTitle"].strip()
    credit = name if prefix in ("CC0", "PD") else f"{name} {version.group(1)}"
    return {
        "title": title,
        "artist": artist,
        "album": album,
        "license": licence,
        "license_url": deed,
        "attribution": f'"{title}" by {artist}, {credit}',
        "quote": quote,
        "file_url": info["fileUrl"],
        **page_metadata(page),
    }


def page_metadata(page: str) -> dict:
    """Genres, release date and cover art link from a track page; any of them may be missing."""
    genres = re.findall(FMA + r'/genre/[^"]+"[^>]*>\s*([^<]+?)\s*<', page)
    released = re.search(r"Released\s*(?:<[^>]+>\s*)*([A-Z][a-z]{2} \d{1,2}, \d{4})", page)
    art = cover_url(page)
    return {
        "genres": list(dict.fromkeys(html.unescape(g) for g in genres)),
        "released": datetime.strptime(released.group(1), "%b %d, %Y").date().isoformat() if released else "",
        "art_url": art,
    }


def cover_url(page: str) -> str:
    """The original file of the track's own cover if it has one, else the album's; '' if neither.
    (The page's resized image links serve WebP labelled as JPEG, so they're not used.)"""
    links = [html.unescape(u) for u in re.findall(FMA + r"/image/\?file=[^\"' ]+", page)]
    for kind in ("type=track", "type=album", "file=album_image"):
        for link in links:
            if kind in link and "type=artist" not in link:
                path = urllib.parse.unquote(re.search(r"file=([^&]+)", link).group(1))
                return f"https://files.freemusicarchive.org/storage-freemusicarchive-org/{path}"
    return ""


def fetch_art(art_url: str, staging: Path, tid: str) -> str:
    """Saves the cover as <id>.art in staging and returns its real type, or '' if there's no usable
    JPEG or PNG. The type comes from the image's own bytes, never the server's label."""
    if not art_url:
        return ""
    try:
        body, _ = fetch(art_url, AUDIO_HOSTS, limit=MAX_ART_BYTES)
    except (ValueError, OSError):
        return ""
    mime = image_mime(body)
    if mime:
        (staging / f"{tid}.art").write_bytes(body)
    return mime


def looks_like_mp3(body: bytes) -> bool:
    """Some FMA files come as application/octet-stream; trust them only if they start like an MP3."""
    return body[:3] == b"ID3" or (len(body) > 1 and body[0] == 0xFF and body[1] & 0xE0 == 0xE0)


def next_id(rows: list[dict[str, str]], prefix: str = "fma") -> str:
    used = [int(r["id"].rsplit("-", 1)[1]) for r in rows if r["id"].startswith(prefix + "-")]
    return f"{prefix}-{max(used, default=0) + 1:04d}"


IA_KEYS = Path("~/.config/abm-radio/ia-s3").expanduser()  # my two archive.org keys, colon-separated; readable only by me


def wayback(url: str) -> str:
    """Asks the Wayback Machine to save the page and returns the snapshot URL, or '' if it failed.
    With my archive.org keys it uses the logged-in save API, since anonymous saves get refused."""
    if os.environ.get("WAYBACK") == "later":  # batch now, snapshot in one slow pass afterwards
        return ""
    if IA_KEYS.is_file():
        return wayback_logged_in(url, IA_KEYS.read_text().strip())
    try:
        with urllib.request.urlopen(urllib.request.Request("https://web.archive.org/save/" + url, headers=UA), timeout=180) as r:
            final = r.geturl()
            return final if "/web/" in final else ""
    except OSError:
        return ""


def wayback_logged_in(url: str, keys: str, wait: float = 5, tries: int = 36) -> str:
    """Save Page Now 2: start a capture job, then poll it until it succeeds or fails (3 min max)."""
    headers = {**UA, "Accept": "application/json", "Authorization": f"LOW {keys}"}

    def get(req: urllib.request.Request) -> dict:
        """Connections to web.archive.org are refused now and then, so each call gets a few goes.
        Errors aren't logged: their text could echo the request."""
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.load(r)
            except (OSError, ValueError):
                time.sleep(wait * (attempt + 1))
        return {}

    data = urllib.parse.urlencode({"url": url}).encode()
    job = get(urllib.request.Request("https://web.archive.org/save", data, headers)).get("job_id")
    for _ in range(tries if job else 0):
        time.sleep(wait)
        s = get(urllib.request.Request(f"https://web.archive.org/save/status/{job}", headers=headers))
        if s.get("status") == "success":
            return f"https://web.archive.org/web/{s['timestamp']}/{s['original_url']}"
        if s.get("status") not in ("pending", None):
            return ""
    return ""


def ingest(url: str, station: str, playlists: str, staging: Path) -> str:
    _, rows = read_csv(TRACKS)
    if any(r["source_url"].rstrip("/") == url.rstrip("/") for r in rows):
        return f"skip (already catalogued): {url}"
    page, _ = fetch(url, PAGE_HOSTS, limit=5 * 1024 * 1024)
    t = parse_track_page(page.decode("utf-8", "replace"), url)
    audio, kind = fetch(t["file_url"], AUDIO_HOSTS)
    if not (kind == "audio/mpeg" or (kind == "application/octet-stream" and looks_like_mp3(audio))):
        raise ValueError(f"audio is {kind!r}, not MP3")  # MP3 only: what FMA serves and what the file name says
    tid = next_id(rows)
    file_name = f"{tid}.mp3"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / file_name).write_bytes(audio)
    meta = {"genres": t["genres"], "released": t["released"], "art_url": t["art_url"], "art_mime": fetch_art(t["art_url"], staging, tid)}
    row_like = {"id": tid, "license": t["license"], "license_url": t["license_url"], "source_url": url}
    tag(staging / file_name, t["title"], t["artist"], t["album"], f'{t["attribution"]}. {url}', extras(row_like, {"page_metadata": meta}, staging))
    digest = sha256(staging / file_name)
    archived = wayback(url)
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        id=tid, title=t["title"], artist=t["artist"], album=t["album"], source="fma", source_url=url,
        license=t["license"], license_url=t["license_url"], attribution=t["attribution"],
        commercial_ok="yes", streaming_ok="yes", downloaded_at=date.today().isoformat(),
        file_name=file_name, sha256=digest, station=station, playlists=playlists, status="pending",
    )  # fmt: skip
    # Re-read just before writing, so an approval made while this track downloaded isn't lost.
    _, rows = read_csv(TRACKS)
    write_tracks([*rows, row])
    evidence = {
        "id": tid,
        "source_url": url,
        "license": t["license"],
        "license_text_quote": t["quote"],
        "archived_url": archived,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_sha256": digest,
        "page_metadata": meta,
    }
    (EVIDENCE / f"{tid}.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    note = "" if archived else " (Wayback save failed; retry before approving)"
    return f"{tid}: {t['artist']} - {t['title']} [{t['license']}]{note}"


def enrich(staging: Path) -> list[str]:
    """Adds page_metadata (and the cover) to pending FMA tracks that lack it, then re-tags all pending files."""
    _, rows = read_csv(TRACKS)
    done = []
    for r in rows:
        ev_path = EVIDENCE / f"{r['id']}.json"
        if r["status"] != "pending" or r["source"] != "fma" or not ev_path.is_file():
            continue
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        art = staging / f"{r['id']}.art"
        if "page_metadata" in ev and art.is_file() and image_mime(art.read_bytes()):
            continue  # already has metadata and a real JPEG or PNG cover
        page, _ = fetch(r["source_url"], PAGE_HOSTS, limit=5 * 1024 * 1024)
        meta = page_metadata(page.decode("utf-8", "replace"))
        art.unlink(missing_ok=True)
        meta["art_mime"] = fetch_art(meta["art_url"], staging, r["id"])
        ev["page_metadata"] = meta
        ev_path.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        done.append(r["id"])
        time.sleep(2)
    tag_pending(staging)
    return done


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--enrich":
        print(f"enriched {len(enrich(Path(sys.argv[2])))} tracks; re-tagged all pending files")
        sys.exit(0)
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
