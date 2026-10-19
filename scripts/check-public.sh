#!/usr/bin/env bash
# This repo is public, so block anything that should never be in it: home-network details
# (private addresses, LAN hostnames and paths, my node names), binary files, commit identities
# other than GitHub no-reply addresses, and writing that isn't in my voice.
#
# Usage: check-public.sh             scan what is staged (pre-commit, CI)
#        check-public.sh --msg FILE  scan a commit message (commit-msg)
#        check-public.sh --history   scan every commit, message and identity on every ref (pre-push, CI)
#
# Two lists stay on my machine (gitignored), so neither ever lands here: .infra-names holds my
# node names (one per line, plain text) and .blocked-words holds wording I never publish (one
# extended regex per line). CI has no copy of either, so it runs every other check (see DECISIONS.md).
#
# The patterns are written so they never match their own source, which lets this file scan
# itself like any other: [x] brackets keep the literal words out.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
names="$repo_root/.infra-names"
words="$repo_root/.blocked-words"

octet='[0-9]{1,3}'
ip="(10\.$octet|192\.168|172\.(1[6-9]|2[0-9]|3[01])|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])|169\.254)\.$octet\.$octet"
ula='(^|[^0-9a-f:])(f[cd][0-9a-f]{2}|fe[89ab][0-9a-f]):[0-9a-f]{0,4}:'
host='[a-z0-9-]+\.(local|localdomain|lan|home|home\.arpa|internal|corp|ts\.net)([^a-z0-9-]|$)'
# A dotless host after any scheme. Two characters minimum: #1's public history has https://x placeholders.
bare_url='[a-z]+://([^/@ ]*@)?[a-z0-9-]{2,}([^a-z0-9.@-]|$)'
lan_path='(^|[^a-z0-9_.~-])/(mnt|srv|media|home|Users)/|\\\\[a-z0-9.-]+\\|[a-z]:\\U[s]ers\\'
voice="(^|[^a-z'])(w[e]|w[e]'re|w[e]'ve|w[e]'ll|o[u]r|o[u]rs|o[u]rselves)([^a-z']|$)"

found=0
hit() { echo "Blocked ($1):" >&2; sed 's/^/    /' >&2; found=1; }

# Each mode defines search (grep flags in, matching lines out); scan runs the infra patterns through it.
check() { local out; out="$(search "${@:2}" || true)"; [[ -z "$out" ]] || hit "$1" <<< "$out"; }
scan() {
    check "private or link-local IP" -iE -e "$ip" -e "$ula"
    check "home-network hostname" -iE -e "$host" -e "$bare_url"
    check "LAN or home path" -iE -e "$lan_path"
    if [[ -s "$names" ]]; then check "node name from .infra-names" -iwF -f "$names"; fi
}
# Writing that isn't mine: first-person plural, plus anything on my local word list.
voice_check() {
    check "writing that isn't mine" -iE -e "$voice"
    if [[ -s "$words" ]]; then check "wording from .blocked-words" -iE -f "$words"; fi
}

case "${1:-}" in
    --msg)
        msg="$(grep -v '^#' "$2" || true)"
        search() { grep -n "$@" <<< "$msg"; }
        scan
        voice_check
        ;;
    --history)
        history="$(git log --all -p --format='commit %H%n%B')"
        search() { grep -n "$@" <<< "$history"; }
        scan
        # GitHub's own merge commits are committed by noreply@github.com; everything else is mine or a bot's no-reply.
        identities="$(git log --all --format='%h author %ae%n%h committer %ce' | grep -vE ' ([0-9]+\+)?[a-z0-9-]+(\[bot\])?@users\.noreply\.github\.com$| noreply@github\.com$' || true)"
        [[ -z "$identities" ]] || hit "commit email that isn't a GitHub no-reply address" <<< "$identities"
        ;;
    "")
        search() { git grep --cached -nI "$@"; }
        scan
        # Third-party data (titles, attribution lines) and the GPL text are not my writing.
        search() { git grep --cached -nI "$@" -- . ':!LICENSE' ':!catalog/' ':!evidence/'; }
        voice_check
        # git grep -I skips binary files, so nothing above can see inside them; this repo has no use for any.
        binaries="$(comm -23 <(git grep --cached -l -e '' | sort) <(git grep --cached -I -l -e '' | sort))"
        [[ -z "$binaries" ]] || hit "binary file (the text checks can't read it)" <<< "$binaries"
        ;;
    *) echo "usage: check-public.sh [--msg FILE | --history]" >&2; exit 2 ;;
esac

exit "$found"
