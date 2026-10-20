# Credits format

The credits page is generated at site build time from `credits.json`, which
`scripts/export_credits.py` writes from the catalog's approved tracks. Nobody edits it by hand.

## credits.json

A JSON array, one object per approved track, sorted by station, artist, title and then id:

```json
[
  {
    "id": "fma-0007",
    "station": "lofi",
    "title": "Cafezinho com Leite",
    "artist": "Popoi",
    "album": "",
    "license": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "source_url": "https://freemusicarchive.org/music/popoi/single/cafezinho-com-leite/",
    "attribution": "\"Cafezinho com Leite\" by Popoi, CC BY 4.0"
  }
]
```

| Field | Use on the page |
|---|---|
| `artist` | group heading |
| `title`, `album` | the track line (album only when present) |
| `license`, `license_url` | the licence, linked to its deed: show `CC BY 4.0`, not the raw id |
| `source_url` | "source" link to where the track came from |
| `attribution` | the exact credit line, also used by the player |
| `station`, `id` | filtering, and stable anchors (`/credits#fma-0007`) |

## The page

- One section per artist, A to Z, with their tracks under them. Artists with an album group the
  tracks by album.
- A station filter once there's more than one station.
- A line at the top saying the list matches what can play right now, and when it was built.
- Every value is rendered as text. Titles and names come from third parties, so nothing from this
  file is ever inserted as HTML or into a `<script>` tag.

## How it gets to the site

`export_credits.py` refuses to run on a catalog that fails validation, so the file only ever lists
tracks with complete licence evidence. How the site repo picks the file up (a copy in each
release, or a fetch at build time from this public repo) is for the site build to decide.
