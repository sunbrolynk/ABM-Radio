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

## Music licences

- **No NC music.** The music library takes only licences without a non-commercial clause: CC0,
  public domain, CC BY, CC BY-SA, CC BY-ND and site licences that allow radio. A lot of lofi is
  NC, so the pool is smaller, but the station never has to worry about what counts as
  commercial, and support links stay possible.
- **CC BY-ND is accepted, played whole and unedited.** Broadcasting a complete track isn't a
  derivative work. Crossfading two tracks and levelling loudness are normal broadcast handling,
  not remixing, so I treat them as playing the work unmodified. Rejected: dropping ND entirely,
  which would cost tracks for no real gain.
- **Removal requests** go to admin@audiobookmanager.com, the address already on the README and
  SECURITY.md.

## Spoken word (for Story Time, after the lofi station)

- **Commercial audiobooks are never aired,** bought or not. A personal licence doesn't include
  public performance, being non-commercial doesn't change that, and removing the DRM to get the
  audio out is its own problem.
- **CC BY-NC-ND 4.0 is accepted for spoken word** while the station stays non-commercial and
  plays every item whole and unedited, with credit. The validator allows it only on the
  `storytime` station and only with `commercial_ok=no`. Music under NC or ND is still undecided
  (below).
- **The Escape Artists shows are checked per episode,** because older episodes were released
  under CC BY-NC-ND 3.0 and Pseudopod's about page states no licence at all. I take only episodes
  whose own page says 4.0. Accepting 3.0 is a separate decision.
- **Internet Archive items are checked one by one.** The uploader sets the rights, not the
  Archive, and many uploads aren't public domain.
- **Fan fiction only with the fan author's written permission,** and even then it can be pulled
  by the original rights holder, so it isn't something I seek out.
- **Indie authors need written permission** (an email is enough), stored as evidence like any
  licence. How a permission is recorded in `tracks.csv` gets decided with the first one.

## The server

- **Host:** a dedicated VM on my home Proxmox server (4 cores, 4 GB RAM, 40 GB system disk), with
  the music on a 750 GB disk carved from a two-drive ZFS mirror reserved for the stations. The
  exact host, addresses and paths live in my private notes.
- **Rejected:** a single music drive (no redundancy), and the Proxmox host's shared VM storage
  (the library could crowd out other VMs).
- **Rejected:** secondhand storage-array drives (520-byte sectors), which the RAID controller
  can't use without a low-level reformat.
- **AzuraCast** uses the official Docker installer on the stable channel. It isn't a Portainer
  stack, because AzuraCast supports only its own installer and updater.
- **Listener data:** analytics collection is **Limited**, so AzuraCast keeps listener totals but
  no per-listener IP statistics, and playback history is kept for 30 days.

## Going public (the plan the launch review checks)

- **One stream hostname for every station:** `stream.audiobookmanager.com`, with each station at
  its own path (`/listen/lofi/…`, `/listen/storytime/…`). Stations don't need hostnames of their
  own.
- **It points straight at my home IP** as a DNS-only (grey-cloud) record, with AzuraCast issuing
  its own TLS certificate. I'm fine with the IP being visible. Rejected for now: a VPS relay in
  front of it. It's worth revisiting only if the home connection is ever attacked or can't keep
  up with listeners.
- **The landing page is a page on my own website** at `radio.audiobookmanager.com`, so I have
  full control over how it looks and works. AzuraCast's own public page stays available for its
  embeddable player. Rejected: pointing the subdomain at AzuraCast's page, which is off-brand and
  has no credits page.
- **Logs keep listener IPs briefly.** AzuraCast already keeps no per-listener analytics. Its web
  server logs still record IPs, so they're capped at roughly a week: enough to look into abuse
  or a fault, not a long-term record of who listened. This gets enforced with Docker's log
  rotation before launch.

## Playlists come from folders

- **Chosen:** folder-based playlists. Each playlist is a folder in AzuraCast's media library,
  linked to that playlist, so what's in the folder is what plays, with no import step to forget
  or drift out of sync.
- **Rejected:** importing M3U files from `export_playlist.py` after every batch. It's an extra
  manual step, and the folders already give the same result. The script stays for rebuilding a
  playlist if it's ever needed.
- **The approval gate:** new files wait in `incoming/`, which isn't linked to any playlist, until
  their row is approved. `check_media.py` fails if any audio file outside `incoming/` lacks an
  approved row with a matching sha256.
- **One playlist to start**, "Lofi", playing all day. A day/night split only pays off once
  there are enough tracks that each half doesn't repeat too often.

## Bringing tracks in

- **Free Music Archive tracks come in through `ingest_fma.py`,** one at a time with a pause
  between them. It reads the track page's own data and licence link, refuses anything that isn't
  CC BY, BY-SA, BY-ND or CC0, saves the page to the Wayback Machine and fetches the audio file the
  page's player uses. Downloading by hand was the alternative, and it doesn't scale past a few
  dozen tracks.
- **The files reach the server through AzuraCast's SFTP,** into `incoming/`, with a key that only
  reaches the station's media. `approve.py` approves tracks only if the whole catalog still
  validates, and prints the moves into the playlist folder.
- **Everything still waits for my ears.** Nothing leaves `incoming/` until I've listened and
  approved it.

## Holiday music

- **Each holiday gets its own playlist and folder,** mixed in at random rather than played in a
  fixed slot: a General Rotation playlist with a low weight, scheduled across the holiday's dates.
  Tested with Halloween in October 2026: the queue mixes Halloween tracks in among the lofi
  without taking over.
- **Rejected:** "once every N songs", which is predictable and was ruled out as not random
  enough.
- **The dates include the year,** so each holiday playlist's schedule is moved forward once a
  year.
- **Sources:** HoliznaCC0's holiday beat tapes are CC0. For *Beats From The Crypt*, the album text
  says "patrons only", but Holizna's Patreon no longer exists and each track page states CC0. I
  accept those tracks as CC0, and each row notes why.

## To do

- **M3U entries are bare file names** that AzuraCast matches on import. That's fine while every
  file name is a unique `<id>.<ext>`. If two stations ever share a media folder, switch to
  media-relative paths.
- **For the site draft:** `credits.json` holds third-party text (titles, artist names,
  attribution lines). The page must render it as text (`textContent`, or a framework's normal
  escaping), never through `innerHTML` and never inlined into a `<script>` tag.


## The kids station only plays what I've marked kid-safe

- **Chosen:** a `kid_safe` column in the catalog, and `validate.py` refuses an approved Lil' Beats FM
  track unless it's `kid_safe=yes`. My review is the move into that station's playlist folder:
  I listen for lyrics, covers and anything unsuitable first.
- **Rejected:** relying on the station alone. A track approved for the wrong station, or a slip in
  sorting, would then play to kids with nothing to catch it.
