# Contributing

## Changes

Work on a branch off `dev` and open a pull request into `dev`; `dev` reaches `main` in a release
pull request. Explain the problem, the change and how you verified it.

Install the hooks once with `bash scripts/install-hooks.sh`, then let them run on every commit and
push:

- **pre-commit:** the secret scan, the public-repo check (no home-network details, no writing that
  isn't mine) and the catalog validator.
- **pre-push:** the same over the whole outgoing range, plus the script tests and the changelog
  check.

Every one has to pass; don't push with `--no-verify`. CI runs the same checks again on the pull
request.

New logic comes with tests in the same pull request. Every commit that changes `scripts/` needs a
`CHANGELOG.md` entry under `Unreleased`, in it or in a later commit on the branch; one with no
effect anyone would notice opts out with a `Changelog: none` trailer.

## Tracks and books

Every item in `catalog/tracks.csv` needs its licence read from its own page, the sentence that
grants use quoted in `evidence/<id>.json`, and a Wayback snapshot of that page. Music must be CC BY,
BY-SA, BY-ND, CC0 or public domain; nothing NonCommercial. Bring items in with the `ingest_*.py`
scripts rather than by hand, and never commit audio.

## Commit messages

Lowercase and imperative, saying what changed against what it replaced, for example
`save wayback snapshots through my account instead of anonymously`.

## Dependencies

The scripts use only the Python standard library. A new dependency gets its own pull request, a
hash-pinned lock, a release at least 14 days old, and a read of the upstream release notes and the
code diff between the published versions. Passing checks alone don't make an update safe.
