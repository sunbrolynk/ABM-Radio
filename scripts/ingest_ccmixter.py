"""Brings ccMixter uploads into the catalog as pending, the same way ingest_fma.py does for FMA: reads
each upload page, refuses any licence I don't accept, saves the page to the Wayback Machine,
downloads the MP3 into a local staging folder and writes the tracks.csv row and evidence file.

Usage: python3 scripts/ingest_ccmixter.py <file of upload page URLs> <station> <playlists> <staging dir>

One URL per line (https://ccmixter.org/files/<user>/<number>); blank lines and lines starting with
# are skipped, and so is any URL already in tracks.csv. Uploads go in one at a time with a pause
between them. Nothing here touches the radio server.
"""

import html
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from catalog import COLUMNS, EVIDENCE, TRACKS, read_csv, write_tracks
from hash_files import sha256
from ingest_fma import PAUSE_S, fetch, looks_like_mp3, next_id, wayback
from tag_mp3 import extras, tag

HOSTS = {"ccmixter.org"}  # pages and files both live there
# creativecommons.org path -> (licence id prefix, human name). NC and Sampling+ are deliberately absent.
LICENCES = {
    "licenses/by/": ("CC-BY", "CC BY"),
    "licenses/by-sa/": ("CC-BY-SA", "CC BY-SA"),
    "licenses/by-nd/": ("CC-BY-ND", "CC BY-ND"),
    "publicdomain/zero/": ("CC0", "CC0"),
    "publicdomain/mark/": ("PD", "Public Domain"),
    "licenses/publicdomain": ("PD", "Public Domain"),
}


def parse_upload_page(page: str, url: str) -> dict[str, str]:
    """Pulls the upload's title, artist, licence and MP3 link out of its page. Raises ValueError if anything is off."""
    box = re.search(r'<div id="license_info_t">(.*?)</div>', page, re.S)
    if not box:
        raise ValueError("no licence box on the page")
    box = box.group(1)
    # The box names the work it licenses; make sure that's this upload and not a remix source.
    own = re.search(r'href="([^"]+)" rel="cc:attributionURL"', box)
    if not own or own.group(1).rstrip("/") != url.rstrip("/"):
        raise ValueError("the licence box is for another upload")
    # ccMixter links the licence twice (text and badge); the site's own NC footer has no rel="license".
    links = {m.group(1).rstrip("/") for m in re.finditer(r'rel="license"[^>]*href="([^"]+)"', page)}
    if len(links) != 1:
        raise ValueError(f"expected exactly one licence link on the page, found {sorted(links) or 'none'}")
    link = re.fullmatch(r"https?://creativecommons\.org/(.+)", links.pop())
    if not link:
        raise ValueError("licence link isn't a Creative Commons one")
    path = link.group(1)
    match = next((v for k, v in LICENCES.items() if path.startswith(k)), None)
    version = re.search(r"/(\d\.\d)$", path)
    if not match or not (version or match[0] == "PD"):
        raise ValueError(f"licence {path!r} is not one I accept")
    prefix, name = match
    licence = {"CC0": "CC0-1.0", "PD": "PD"}.get(prefix) or f"{prefix}-{version.group(1)}"
    title = re.search(r'property="dc:title"[^>]*>([^<]+)<', box)
    artist = re.search(r'property="cc:attributionName">([^<]+)<', box)
    if not (title and artist):
        raise ValueError("no title or artist in the licence box")
    title, artist = html.unescape(title.group(1)).strip(), html.unescape(artist.group(1)).strip()
    # The page's play button gets the upload's own MP3 from a one-line script keyed by the upload number.
    upload = url.rstrip("/").rsplit("/", 1)[1]
    mp3 = re.search(r"\$\('_ep_" + re.escape(upload) + r"'\)\.href = '([^']+)'", page)
    if not mp3:
        raise ValueError("no MP3 link for this upload on the page")
    # Tags go without a space, so the quoted title stays "Title"; the box has whitespace between lines.
    quote = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", box))).strip()
    quote = re.sub(r"\s+([.,])", r"\1", quote)
    uploaded = re.search(r"uploaded: \w{3}, (\w{3} \d{1,2}, \d{4})", page)
    credit = name if prefix in ("CC0", "PD") else f"{name} {version.group(1)}"
    return {
        "title": title,
        "artist": artist,
        "license": licence,
        "license_url": f"https://creativecommons.org/{path}/",
        "attribution": f'"{title}" by {artist}, {credit}',
        "quote": quote,
        "file_url": html.unescape(mp3.group(1)),
        "released": datetime.strptime(uploaded.group(1), "%b %d, %Y").date().isoformat() if uploaded else "",
    }


def ingest(url: str, station: str, playlists: str, staging: Path) -> str:
    _, rows = read_csv(TRACKS)
    if any(r["source_url"].rstrip("/") == url.rstrip("/") for r in rows):
        return f"skip (already catalogued): {url}"
    page, _ = fetch(url, HOSTS, limit=5 * 1024 * 1024)
    t = parse_upload_page(page.decode("utf-8", "replace"), url)
    # ccMixter answers 403 to a file request that doesn't come from its own page.
    audio, kind = fetch(t["file_url"], HOSTS, headers={"Referer": url})
    if not (kind == "audio/mpeg" or (kind == "application/octet-stream" and looks_like_mp3(audio))):
        raise ValueError(f"audio is {kind!r}, not MP3")
    tid = next_id(rows, "ccm")
    file_name = f"{tid}.mp3"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / file_name).write_bytes(audio)
    meta = {"genres": [], "released": t["released"], "art_url": "", "art_mime": ""}  # ccMixter has no cover art
    row_like = {"id": tid, "license": t["license"], "license_url": t["license_url"], "source_url": url}
    tag(staging / file_name, t["title"], t["artist"], "", f'{t["attribution"]}. {url}', extras(row_like, {"page_metadata": meta}, staging))
    digest = sha256(staging / file_name)
    archived = wayback(url)
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        id=tid, title=t["title"], artist=t["artist"], source="ccmixter", source_url=url,
        license=t["license"], license_url=t["license_url"], attribution=t["attribution"],
        commercial_ok="yes", streaming_ok="yes", downloaded_at=date.today().isoformat(),
        file_name=file_name, sha256=digest, station=station, playlists=playlists, status="pending",
    )  # fmt: skip
    # Re-read just before writing, so an approval made while this upload downloaded isn't lost.
    _, rows = read_csv(TRACKS)
    write_tracks([*rows, row], TRACKS)
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


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: ingest_ccmixter.py <url file> <station> <playlists> <staging dir>")
    urls = [u.strip() for u in Path(sys.argv[1]).read_text().splitlines() if u.strip() and not u.startswith("#")]
    failed = 0
    for i, u in enumerate(urls):
        try:
            print(ingest(u, sys.argv[2], sys.argv[3], Path(sys.argv[4])), flush=True)
        except (ValueError, OSError, KeyError) as e:
            failed += 1
            print(f"REFUSED {u}: {e}", file=sys.stderr, flush=True)
        if i < len(urls) - 1:
            time.sleep(PAUSE_S)
    sys.exit(1 if failed else 0)
