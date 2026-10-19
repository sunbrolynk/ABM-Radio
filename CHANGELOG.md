# Changelog

All notable changes to the ABM Radio scripts are recorded here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `validate.py`, which checks `catalog/tracks.csv` and the licence evidence before anything
  can go on air.
- Commit and push hooks that block secrets, home-network details and broken catalogs.
