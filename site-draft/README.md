# Site draft: radio.audiobookmanager.com

My draft for the station page, for the
[audiobookmanager.com](https://github.com/sunbrolynk/AudioBookManager.com) repo to build from. It's a
starting point to shape, not a finished design. The page lives on my own site so I have full
control over how it looks and works; AzuraCast only supplies the audio and the live data.

| File | What it covers |
|---|---|
| [`page-copy.md`](page-copy.md) | The words on the page, in my voice |
| [`player-spec.md`](player-spec.md) | How the player behaves and where it gets its data |
| [`credits-format.md`](credits-format.md) | The credits page and the `credits.json` it's built from |

The ground rules from [`docs/website.md`](../docs/website.md) apply throughout: no tracking, no
donation buttons on the radio page or in the player, and every piece of third-party text rendered
as text, never as HTML.

## Layout

```
radio.audiobookmanager.com/            all stations, one card each
radio.audiobookmanager.com/lofi        ABM Lofi: player, recent tracks, about
radio.audiobookmanager.com/credits     every track that can play, grouped by artist
radio.audiobookmanager.com/storytime   later
```

It matches the main site's look: the same header, footer and fonts (Cinzel for headings, Spectral
for text), the same dark theme, and the ABM logo.
