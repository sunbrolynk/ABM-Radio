# ABM Radio

The catalog behind ABM Radio, the internet radio stations at
[radio.audiobookmanager.com](https://radio.audiobookmanager.com). The first one is ABM Lofi.

Every track that plays is listed here with its licence and proof of that licence, captured
when I downloaded it. Only openly licensed music goes on air (CC0, public domain, CC BY,
CC BY-SA, or a site licence that explicitly allows internet radio). There is no audio in this
repo: the files live on the station's own storage.

## What's in here

- `catalog/tracks.csv`: one row per track, the source of truth. Only `approved` rows play.
- `catalog/sources.csv`: the sites and labels the music comes from, with their licence terms.
- `evidence/<id>.json`: the licence evidence for each track (archived source page, the exact
  sentence that grants use, and the file's sha256).
- `scripts/validate.py`: checks the catalog. It runs on every commit and push, and in CI.

## Adding a track

1. Download the original file and rename it to `<id>.<ext>`, e.g. `chillhop-0001.mp3`.
2. Add a row to `catalog/tracks.csv` with `status=pending`.
3. Save the source page and the licence page with the Wayback Machine and write
   `evidence/<id>.json`.
4. Put the file on the station's storage and fill in its sha256.
5. Run `python3 scripts/validate.py`, then review it and set `status=approved` and
   `reviewed_by`.
6. Commit on a branch off `dev` and open a PR into `dev`.

Run `bash scripts/install-hooks.sh` once after cloning. The hooks need `python3` and either
Docker or gitleaks 8.30.0.

## Artists: removing a track

If you're an artist and want a track taken off the air, email
[admin@audiobookmanager.com](mailto:admin@audiobookmanager.com) and I'll remove it.

## Licence

The scripts are GPL-3.0 (see `LICENSE`). The catalog data describes third-party works, and
each of those works stays under its own licence, listed in `catalog/tracks.csv`.
