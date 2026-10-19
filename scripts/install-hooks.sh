#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$repo_root"

if git config --get core.hooksPath >/dev/null; then
    echo "Custom core.hooksPath detected. Review that configuration before installing." >&2
    exit 1
fi

# Check both hooks before writing either, so a refusal leaves the existing hooks as they were.
for name in pre-commit commit-msg pre-push; do
    hook="$(git rev-parse --path-format=absolute --git-path "hooks/$name")"
    if [[ -e "$hook" || -L "$hook" ]]; then
        if [[ -L "$hook" ]] || ! cmp -s "scripts/$name" "$hook"; then
            echo "An existing, different $name hook needs manual review: $hook" >&2
            exit 1
        fi
    fi
done
for name in pre-commit commit-msg pre-push; do
    install -m 0755 "scripts/$name" "$(git rev-parse --path-format=absolute --git-path "hooks/$name")"
done
echo "Installed the pre-commit, commit-msg and pre-push checks."
