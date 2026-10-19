# Changelog

All notable changes to the ABM Radio scripts are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `validate.py`, which checks `catalog/tracks.csv` and the licence evidence before anything
  can go on air.
- Commit and push hooks that block secrets, home-network details and broken catalogs.
- The public-repo check also blocks link-local and IPv6 private addresses, Tailscale and bare-host
  URLs, LAN paths, binary files, and commit emails that aren't GitHub no-reply addresses.

### Fixed

- `validate.py` no longer accepts an id with a trailing newline, and reports a `sources.csv`
  without a `key` column instead of crashing.
- `install-hooks.sh` now updates its own hooks after they change, instead of refusing.
