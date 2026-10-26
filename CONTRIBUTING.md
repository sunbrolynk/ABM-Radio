# Contributing

## Changes

Work on a branch off `dev` and open a pull request into `dev`; `dev` reaches `main` in a release
pull request. Explain the problem, the change and how you verified it.

Install the hooks once with `bash scripts/install-hooks.sh`, then let them run on every commit and
push:

- **pre-commit:** the secret scan, the public-repo check (no home-network details, no writing that
  isn't mine) and the catalog validator, on what's staged.
- **commit-msg:** the public-repo check on the message.
- **pre-push:** the secret scan and public-repo check over the whole history, the changelog check
  over the commits being pushed, the script tests and the catalog validator, on a clean tree.

Every one has to pass; don't push with `--no-verify`. CI runs the same checks again on the pull
request, apart from my local lists of names and wording.

New logic comes with tests in the same pull request. Every commit that changes `scripts/` needs a
changelog entry, in it or in a later commit on the branch: a `changelog.d/<slug>.<section>.md` file
(a short name such as the branch name without its `feat/` prefix; section `added`, `changed`,
`fixed`, `removed` or `security`) holding the bullet as it should read, bold lead phrase first, so
parallel pull requests don't conflict in `CHANGELOG.md`. I fold them in under `Unreleased` at
release time with `python3 scripts/collate-changelog.py` (`--dry-run` to preview). A commit with no
effect anyone would notice opts out with a `Changelog: none` trailer.

## Tracks and books

Every item in `catalog/tracks.csv` needs its licence read from its own page, the sentence that
grants use quoted in `evidence/<id>.json`, and a Wayback snapshot of that page. Music must be under a
licence listed in [LICENSES.md](LICENSES.md); nothing NonCommercial. Bring items in with an
`ingest_*.py` script where one exists for the source, and never commit audio.

## Commit messages

Lowercase and imperative, saying what changed against what it replaced, for example
`save wayback snapshots through my account instead of anonymously`.

## Dependencies

The scripts use only the Python standard library. A new dependency gets its own pull request, a
hash-pinned lock, a release at least 14 days old, and a read of the upstream release notes and the
code diff between the published versions. Passing checks alone don't make an update safe.
