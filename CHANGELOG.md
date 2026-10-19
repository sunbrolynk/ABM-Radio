# Changelog

All notable changes to the ABM Radio scripts are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `validate.py`, which checks `catalog/tracks.csv` and the licence evidence before anything
  can go on air.
- `hash_files.py`, `export_credits.py` and `export_playlist.py`, which fill in each file's hash
  and write the credits and per-station playlists from approved tracks only.
- Commit and push hooks that block secrets, home-network details and broken catalogs.
- The public-repo check also blocks link-local and IPv6 private addresses, Tailscale and other
  LAN hostnames, dotless hosts after any URL scheme, LAN and home-folder paths, binary files, and
  commit emails that aren't GitHub no-reply addresses.

### Fixed

- A `file_name` must be a plain lowercase `<id>.<ext>`, so it can't carry a path or inject a line
  into a playlist.
- `hash_files.py` skips symlinks, writes evidence atomically and only after the catalog, and
  reports evidence captured for a different file instead of leaving it silently.
- Credits with the same artist and title now sort by id, so the output is stable.

- `validate.py` no longer accepts an id with a trailing newline, and reports a `sources.csv`
  without a `key` column instead of crashing.
- `install-hooks.sh` now updates its own hooks after they change, instead of refusing.
