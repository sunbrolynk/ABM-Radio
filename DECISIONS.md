# Decisions

What I decided for ABM Radio, what I turned down, and why. Server specifics (host names, addresses,
paths) live in my private notes, never here.

## The repo is public from the first commit

- **Chosen:** public. GitHub's free plan only gives branch rulesets, secret scanning, push
  protection and private vulnerability reports to public repos, and the catalog was always going
  to be public: the licences and credits are public anyway.
- **Rejected:** private until launch. It would have meant no ruleset and no push protection
  while the catalog was being built, which is when mistakes are most likely.
- **Rejected:** paying for GitHub Pro just to keep it private for a few weeks.
- **What it costs:** nothing about my network can ever be committed. `scripts/check-public.sh`
  blocks private and link-local addresses (IPv4 and IPv6), LAN hostnames and bare-host URLs, LAN
  paths, my node names, binary files, and any commit email that isn't a GitHub no-reply address.

## Known limits of the public-repo checks

- **Node names and my blocked wording are checked on my machine only.** They come from
  `.infra-names` and `.blocked-words`, which are gitignored so the lists never land here. CI has
  no copy, so CI runs every other check but not those two. I turned down a hashed list in the repo: a short node name falls to a dictionary
  attack against its hash, which would publish the very name it protects. A repo secret would
  work but adds a secret to a repo that has none, so the commit and push hooks carry this check.
- **Binary files are blocked outright** instead of scanned, since the text checks can't read
  them and the repo has no use for any. Audio is also gitignored. If the site draft ever needs an
  image, that's a decision for its own PR.
- **History can't be rewritten** once pushed, so the history scan matches only patterns precise
  enough not to trip on what is already public.

## Secret scanning without Docker

- **Chosen:** the hooks run the pinned gitleaks Docker image when Docker is there, and otherwise
  the gitleaks 8.30.0 binary, the same version, checked against the release's published
  checksums.
- **Rejected:** skipping the scan where Docker is missing.

## To do

- **M3U entries are bare file names** that AzuraCast matches on import. That's fine while every
  file name is a unique `<id>.<ext>`. If two stations ever share a media folder, switch to
  media-relative paths.
- **For the site draft:** `credits.json` holds third-party text (titles, artist names,
  attribution lines). The page must render it as text (`textContent`, or a framework's normal
  escaping), never through `innerHTML` and never inlined into a `<script>` tag.

## Still to decide (handoff §11)

1. Host machine and storage path (described here only generically).
2. NC music, and whether the station ever takes donations.
3. ND music.
4. Folder-based playlists or M3U import.
5. Stream hostname, and whether a DNS-only record exposing my IP is OK.
6. Landing page: a page on the site, or AzuraCast's own public page.
7. The removal-request contact address.
8. Listener-IP log retention.
