# Changelog

All notable changes to the ABM Radio scripts are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Wayback snapshots go through my archive.org account when its keys are on this machine, since
  anonymous saves get refused, and a refused connection is retried instead of failing the save.
  `WAYBACK=later` skips the save during a big batch, so the snapshots can follow in one slow pass.

- Halloween: 15 approved tracks plus 10 pending, and the holiday-playlist method in
  DECISIONS.md and the server guide, with a troubleshooting section.

- `site-draft/`: page copy, a player spec and the credits format for radio.audiobookmanager.com.

- Every track's tag also carries its genre, release year, cover art, licence (copyright field and
  licence link) and FMA source link. `ingest_fma.py --enrich` backfills them for tracks already
  downloaded.

- `tag_mp3.py`, which writes the catalog's title, artist, album and credit into each MP3's tag, so
  the station shows the right credit for files that arrive untagged. The ingest tags every track
  before hashing it.

- `ingest_fma.py` and `approve.py`, which bring Free Music Archive tracks in as pending with their
  licence proof, then approve them in bulk.

- The going-public plan: one stream hostname at my home IP, the landing page on my own site, and
  IP-bearing logs kept about a week.
- CC BY-ND music is accepted, played unedited. NC music never is.

- `check_media.py`, which fails if any audio file on the server outside `incoming/` lacks an
  approved row with a matching sha256.

- The server guide now covers the Ubuntu install, the music disk, AzuraCast's install and
  settings, the station, its streams and both backup layers, and DECISIONS.md records the server
  choices.

- A README with the AudioBook Manager branding, plus from-scratch guides for the server
  (`docs/server-setup.md`) and the website side (`docs/website.md`).

- Spoken-word sources for Story Time (LibriVox, the Escape Artists shows, public-domain Internet
  Archive audio), with CC BY-NC-ND 4.0 accepted on the `storytime` station only.

- `validate.py`, which checks `catalog/tracks.csv` and the licence evidence before anything
  can go on air.
- `hash_files.py`, `export_credits.py` and `export_playlist.py`, which fill in each file's hash
  and write the credits and per-station playlists from approved tracks only.
- Commit and push hooks that block secrets, home-network details and broken catalogs.
- The public-repo check also blocks link-local and IPv6 private addresses, Tailscale and other
  LAN hostnames, dotless hosts after any URL scheme, LAN and home-folder paths, binary files, and
  commit emails that aren't GitHub no-reply addresses.

### Fixed

- The history check ignores the trailing context in git's hunk headers, which git cuts at an
  arbitrary width and which once ended mid-URL, looking like a bare hostname.

- FMA's resized cover links serve WebP labelled as JPEG, which players and Liquidsoap can't read
  inside an MP3. Covers now come from FMA's original image file, and an image's type is taken from
  its own bytes: only real JPEG and PNG are embedded. Broken covers are replaced, and
  `tag_mp3.py --fix-approved-art` repairs approved files, refusing any change to the audio bytes.

- FMA serves some artists' files as `application/octet-stream`. The ingest now accepts those only
  when the bytes start like an MP3, instead of refusing them.

- The public-check tests strip git's hook variables (`GIT_DIR` and friends). Run inside a hook,
  they could otherwise act on the real repo instead of their throwaway one.

- The ingest re-reads the catalog just before writing a track's row, so an approval made while a
  track was downloading isn't overwritten.

- `ingest_fma.py` only fetches over https from FMA's own hosts (redirects included), caps
  downloads at 50 MB, accepts only MP3 audio, and refuses a page showing more than one licence.
  `approve.py` says plainly when a failed Wayback save is what's blocking an approval.

- A `file_name` must be a plain lowercase `<id>.<ext>`, so it can't carry a path or inject a line
  into a playlist.
- `hash_files.py` skips symlinks, writes evidence atomically and only after the catalog, and
  reports evidence captured for a different file instead of leaving it silently.
- The list of wording I never publish moved to a local, gitignored file, like my node names.
- Credits with the same artist and title now sort by id, so the output is stable.

- `validate.py` no longer accepts an id with a trailing newline, and reports a `sources.csv`
  without a `key` column instead of crashing.
- `install-hooks.sh` now updates its own hooks after they change, instead of refusing.
