# Player spec

A small custom player built into the station page, not an iframe of AzuraCast's own player, so it
matches the site. It needs no framework, and works with JavaScript off as a plain audio element.

## Audio

- Source: `https://stream.audiobookmanager.com/listen/lofi/radio.aac` (AAC 96 kbps), falling back
  to `radio.mp3` (MP3 128 kbps) if the browser can't play AAC.
- Nothing plays until the listener presses play: no autoplay.
- Controls: play/pause and volume, both reachable by keyboard and labelled for screen readers.
  Pausing a live stream and resuming jumps back to live, which is expected.
- No donation or support buttons anywhere in the player (see `docs/website.md`).

## Live data

AzuraCast's public now-playing API, read only from the page:

```
GET https://stream.audiobookmanager.com/api/nowplaying/lofi
```

Poll it every 15 seconds while the page is visible, and pause polling when the tab is hidden.
AzuraCast's server-sent events can replace polling later, once "High-Performance Now Playing
Updates" is turned on. The API only allows `https://radio.audiobookmanager.com` as an origin
(CORS).

Fields used:

| Shows | From the API |
|---|---|
| Title, artist | `now_playing.song.title`, `now_playing.song.artist` |
| Cover | `now_playing.song.art` (an AzuraCast image URL) |
| Progress | `now_playing.elapsed` / `now_playing.duration` |
| Up next | `playing_next.song.title`, `.artist` |
| Last five tracks | `song_history[0..4].song.title`, `.artist` |
| Listeners (optional) | `listeners.current` |
| Offline state | `is_online` false: show "Off air" instead of a track |

## The credit line

CC BY asks for credit where the music plays, so the player shows each track's attribution line
under the title, with a link to its source page. The API doesn't carry it, so it comes from
`credits.json` (see `credits-format.md`): match the now-playing track by **artist and title**
(compared case-insensitively, trimmed). If there's no match, show only the title and artist. A
track missing from the credits never breaks the player.

## Failure behaviour

- If the API can't be reached, keep the audio playing and show the last known track, greyed out.
- If the stream drops, show "Reconnecting…" and retry with a growing delay (2 s, then 5, 10, 30).
- Everything from the API or `credits.json` goes into the page as text (`textContent`), never
  `innerHTML`.
