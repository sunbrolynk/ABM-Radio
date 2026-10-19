"""Checks tracks.csv and the evidence files. Exits 1 on any problem, so it can gate commits."""

import json
import re
import sys
from pathlib import Path

from catalog import COLUMNS, EVIDENCE, SOURCES, TRACKS, read_csv

# What I accept is written up in LICENSES.md. NC and ND stay out of the music until DECISIONS.md
# says otherwise; spoken word may use CC BY-NC-ND 4.0 while the station is non-commercial.
LICENSE_RE = re.compile(r"^(CC0-1\.0|PD|CC-BY(-SA)?-(2\.0|2\.5|3\.0|4\.0)|SITE:[a-z0-9-]+)$")
SPOKEN_LICENSE_RE = re.compile(r"^CC-BY-NC-ND-4\.0$")
SPOKEN_STATIONS = {"storytime"}
# The id becomes a file name, so keep it to plain lowercase words joined by dashes.
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# A plain <id>.<ext> file name: no paths, and no control characters to break an M3U line.
FILE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.[a-z0-9]+$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
STATUSES = {"pending", "approved", "rejected"}
EVIDENCE_KEYS = {"id", "source_url", "license", "license_text_quote", "archived_url", "captured_at", "file_sha256"}


def validate(tracks: Path = TRACKS, sources: Path = SOURCES, evidence: Path = EVIDENCE) -> list[str]:
    header, rows = read_csv(tracks)
    if header != COLUMNS:
        return [f"tracks.csv header must be exactly: {','.join(COLUMNS)}"]
    source_header, source_rows = read_csv(sources)
    if "key" not in source_header:
        return ["sources.csv needs a key column"]
    source_keys = {s["key"] for s in source_rows}
    errors: list[str] = []
    seen: set[str] = set()
    for line, r in enumerate(rows, start=2):
        tid = r["id"]
        err = lambda msg: errors.append(f"tracks.csv line {line} ({tid or 'no id'}): {msg}")  # noqa: E731
        if None in r or any(r[c] is None for c in COLUMNS):
            err("wrong number of fields")
            continue
        if not ID_RE.fullmatch(tid):
            err("id must be lowercase letters/digits joined by dashes")
        if tid in seen:
            err("duplicate id")
        seen.add(tid)
        if not ID_RE.fullmatch(r["station"]):
            err("station must be a lowercase-dashed name, e.g. lofi")
        for c in ("title", "artist", "source", "source_url", "license", "downloaded_at", "file_name"):
            if not r[c]:
                err(f"{c} is empty")
        if r["status"] not in STATUSES:
            err(f"status must be one of {sorted(STATUSES)}")
        for c in ("commercial_ok", "streaming_ok"):
            if r[c] not in ("yes", "no"):
                err(f"{c} must be yes or no")
        if r["file_name"] and not (FILE_RE.fullmatch(r["file_name"]) and r["file_name"].startswith(tid + ".")):
            err("file_name must be <id>.<ext>, lowercase, with no path")
        if any(not ID_RE.fullmatch(p) for p in r["playlists"].split(";") if p):
            err("playlists must be lowercase-dashed names separated by ;")
        if r["sha256"] and not SHA_RE.fullmatch(r["sha256"]):
            err("sha256 is not a lowercase sha256 hex digest")
        if r["status"] == "rejected":
            continue  # a rejected row only has to stay well-formed; its licence may be why it was rejected
        if r["source"] and r["source"] not in source_keys:
            err(f"source {r['source']!r} is not in sources.csv")
        spoken_ok = r["station"] in SPOKEN_STATIONS and SPOKEN_LICENSE_RE.fullmatch(r["license"])
        if not (LICENSE_RE.fullmatch(r["license"]) or spoken_ok):
            err(f"license {r['license']!r} is not on the accepted list for station {r['station']!r}")
        if "-NC" in r["license"] and r["commercial_ok"] != "no":
            err("a non-commercial licence needs commercial_ok=no")
        if r["license"].startswith("CC-BY") and not r["attribution"]:
            err("CC BY needs an attribution line")
        if r["status"] == "approved":
            if r["streaming_ok"] != "yes":
                err("approved tracks need streaming_ok=yes")
            if not r["reviewed_by"]:
                err("approved tracks need reviewed_by")
            if not r["sha256"]:
                err("approved tracks need a sha256 (run hash_files.py)")
            errors.extend(f"tracks.csv line {line} ({tid}): {e}" for e in check_evidence(r, evidence))
    return errors


def check_evidence(r: dict[str, str], evidence: Path) -> list[str]:
    path = evidence / f"{r['id']}.json"
    if not path.is_file():
        return [f"missing {path.name}"]
    try:
        ev = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"{path.name} is not valid JSON: {e}"]
    if not isinstance(ev, dict):
        return [f"{path.name} must be a JSON object"]
    errors = [f"{path.name} is missing {k}" for k in sorted(EVIDENCE_KEYS - ev.keys())]
    errors += [f"{path.name} has an empty {k}" for k in sorted(EVIDENCE_KEYS & ev.keys()) if not ev[k]]
    for k, col in (("id", "id"), ("file_sha256", "sha256"), ("license", "license"), ("source_url", "source_url")):
        if ev.get(k) and ev[k] != r[col]:
            errors.append(f"{path.name} {k} does not match tracks.csv {col}")
    return errors


if __name__ == "__main__":
    problems = validate()
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        sys.exit(1)
    print("catalog OK")
