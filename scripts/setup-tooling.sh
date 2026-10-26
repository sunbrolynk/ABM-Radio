#!/usr/bin/env bash
# Creates .venv-tooling/ with the lint tools pinned in requirements-tooling.lock; the hooks and CI run ruff from it.
set -euo pipefail

cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"

python3 -m venv .venv-tooling
# The venv ignores itself, so it never shows as untracked on a branch whose .gitignore predates it.
printf '*\n' > .venv-tooling/.gitignore
.venv-tooling/bin/pip install --quiet --require-hashes -r requirements-tooling.lock
echo "Tooling ready: $(.venv-tooling/bin/ruff --version)"
