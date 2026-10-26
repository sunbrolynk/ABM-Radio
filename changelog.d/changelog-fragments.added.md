- **Changelog fragments:** a change can add one `changelog.d/<slug>.<section>.md` file holding its
  bullet instead of editing `CHANGELOG.md`, so parallel pull requests stop conflicting there.
  `collate-changelog.py` folds them under `[Unreleased]` at release time, and `check-changelog.sh`
  takes a fragment as coverage the same way it takes a `CHANGELOG.md` entry.
