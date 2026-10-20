# The website side

How the public page at [radio.audiobookmanager.com](https://radio.audiobookmanager.com) fits
together with the stations. The page itself is built in the
[audiobookmanager.com](https://github.com/sunbrolynk/audiobookmanager.com) repo; this repo only
supplies its data and the plan.

## Hostnames

| Hostname | Serves |
|---|---|
| `radio.audiobookmanager.com` | The public page, with each station at `/lofi`, `/storytime` and so on. |
| `stream.audiobookmanager.com` | AzuraCast itself: the audio streams and the now-playing API. |

Long-running audio streams shouldn't go through Cloudflare's proxy, so the stream hostname is a
DNS-only record and AzuraCast issues its own TLS certificate. The page stays behind Cloudflare as
usual.

## The page

- **Player:** play/pause, volume, the current track (title, artist, attribution line, link to
  the source), the last five tracks, and optionally the listener count. It reads AzuraCast's
  now-playing API, so AzuraCast must allow the page's origin (CORS).
- **Credits:** every approved track, grouped by artist, with title, licence, link and
  attribution. Generated at build time from `out/credits.json`, never kept by hand.
- **Removal policy:** an artist who wants a track removed emails
  [admin@audiobookmanager.com](mailto:admin@audiobookmanager.com) and it comes off the air.
- **No donation buttons on the radio page or in the player** while anything under a
  non-commercial (NC) licence can be on air, which includes Story Time's CC BY-NC-ND episodes. A
  donate button next to an NC stream is the grey area those licences warn about. Support links
  for AudioBook Manager's development belong on the main site and in the repo README, not here.
- **Privacy:** no tracking on the page. AzuraCast logs listener IPs, and how long it keeps them
  is set in AzuraCast.

## Credits data

`python3 scripts/export_credits.py` writes `out/credits.json`: a list of approved tracks, sorted
by station, artist, title and id, each with `id`, `station`, `title`, `artist`, `album`,
`license`, `license_url`, `source_url` and `attribution`.

That file holds third-party text (titles, names, attribution lines), so the page renders it as
text only: `textContent`, or a framework's normal escaping. Never `innerHTML`, and never inlined
into a `<script>` tag.
