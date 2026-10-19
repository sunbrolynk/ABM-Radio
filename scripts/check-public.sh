#!/usr/bin/env bash
# This repo is public, so block anything that should never be in it: home-network details
# (private IPs, .local/.lan names, my node names) and writing that isn't in my voice ("we",
# AI/Claude markers, Co-Authored-By trailers).
#
# Usage: check-public.sh             scan what is staged (pre-commit, CI)
#        check-public.sh --msg FILE  scan a commit message (commit-msg)
#        check-public.sh --history   scan every commit and message on every ref (pre-push, CI)
#
# Node names come from .infra-names (one per line, gitignored), so the list itself never lands here.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
names="$repo_root/.infra-names"

ip='(10\.[0-9]{1,3}|192\.168|172\.(1[6-9]|2[0-9]|3[01])|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7]))\.[0-9]{1,3}\.[0-9]{1,3}'
host='[a-z0-9-]+\.(local|lan|home\.arpa|internal)([^a-z0-9-]|$)'
voice="(^|[^a-z'])(we|we're|we've|we'll|our|ours|ourselves)([^a-z']|$)"
marker='co-authored-by|claude|anthropic|generated with|🤖'

found=0
hit() { echo "Blocked ($1):" >&2; sed 's/^/    /' >&2; found=1; }

# Each mode defines search (grep flags in, matching lines out); scan runs the infra patterns through it.
check() { local out; out="$(search "${@:2}" || true)"; [[ -z "$out" ]] || hit "$1" <<< "$out"; }
scan() {
    check "private IP" -iE -e "$ip"
    check "home-network hostname" -iE -e "$host"
    if [[ -s "$names" ]]; then check "node name from .infra-names" -iwF -f "$names"; fi
}

case "${1:-}" in
    --msg)
        msg="$(grep -v '^#' "$2" || true)"
        search() { grep -n "$@" <<< "$msg"; }
        scan
        check "voice or AI marker in the commit message" -iE -e "$voice" -e "$marker"
        ;;
    --history)
        history="$(git log --all -p --format='commit %H%n%B')"
        search() { grep -n "$@" <<< "$history"; }
        scan
        ;;
    "")
        # Third-party data (titles, attribution lines) and the GPL text are not my writing.
        search() { git grep --cached -nI "$@" -- . ':!scripts/check-public.sh'; }
        scan
        search() { git grep --cached -nI "$@" -- . ':!scripts/check-public.sh' ':!LICENSE' ':!catalog/' ':!evidence/'; }
        check "voice or AI marker" -iE -e "$voice" -e "$marker"
        ;;
    *) echo "usage: check-public.sh [--msg FILE | --history]" >&2; exit 2 ;;
esac

exit "$found"
