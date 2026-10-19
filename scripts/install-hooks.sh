#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$repo_root"

if git config --get core.hooksPath >/dev/null; then
    echo "Custom core.hooksPath detected. Review that configuration before installing." >&2
    exit 1
fi

marker="# abm-radio hook:"

# Check all three hooks before writing any, so a refusal leaves the existing hooks as they were.
# A hook carrying the marker is one of mine (maybe an older version) and gets replaced; anything
# else is someone else's hook and needs a look first.
for name in pre-commit commit-msg pre-push; do
    hook="$(git rev-parse --path-format=absolute --git-path "hooks/$name")"
    if [[ -L "$hook" ]] || { [[ -e "$hook" ]] && ! grep -qF "$marker" "$hook"; }; then
        echo "An existing $name hook that isn't from this repo needs manual review: $hook" >&2
        exit 1
    fi
done
for name in pre-commit commit-msg pre-push; do
    install -m 0755 "scripts/$name" "$(git rev-parse --path-format=absolute --git-path "hooks/$name")"
done
echo "Installed the pre-commit, commit-msg and pre-push checks."
