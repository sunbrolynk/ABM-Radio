<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/readme/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/readme/banner-light.svg">
    <img src="docs/readme/banner-dark.svg" alt="AudioBook Manager" width="560">
  </picture>
</p>

<p align="center"><b>ABM Radio: openly licensed internet radio from AudioBook Manager.</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/status-setting%20up-orange?style=for-the-badge" alt="Status: setting up">
  <img src="https://img.shields.io/badge/powered%20by-AzuraCast-blue?style=for-the-badge" alt="Powered by AzuraCast">
  <img src="https://img.shields.io/badge/python-3.12-blue?style=for-the-badge" alt="Python 3.12">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPLv3-8b45c6?style=for-the-badge" alt="GPLv3 license"></a>
</p>

<p align="center">
  <a href="https://github.com/sunbrolynk/abm-radio/actions/workflows/checks.yml"><img src="https://github.com/sunbrolynk/abm-radio/actions/workflows/checks.yml/badge.svg?branch=dev" alt="Checks"></a>
</p>

<p align="center">
  <a href="#-whats-in-here">What's in here</a> •
  <a href="#-adding-a-track">Adding a track</a> •
  <a href="docs/server-setup.md">Server setup</a> •
  <a href="docs/website.md">Website</a> •
  <a href="LICENSES.md">Licences</a>
</p>

<hr>

ABM Radio is a set of self-hosted internet radio stations, starting with **ABM Lofi**: lofi beats
for listening while you sort your audiobooks. The stations run on
[AzuraCast](https://www.azuracast.com), and the page lives at
[radio.audiobookmanager.com](https://radio.audiobookmanager.com).

This repo is the station's paper trail. Every track that plays is listed here with its licence
and proof of that licence, captured when I downloaded it. Only openly licensed music goes on air:
CC0, public domain, CC BY, CC BY-SA, or a site licence that explicitly allows internet radio. There
is no audio in this repo; the files live on the station's own storage.

## 📦 What's in here

| Path | What it is |
|---|---|
| `catalog/tracks.csv` | One row per track, the source of truth. Only `approved` rows play. |
| `catalog/sources.csv` | The sites and labels the music comes from, with their licence terms. |
| `evidence/<id>.json` | Proof of each licence: the archived source page, the exact sentence that grants use, and the file's sha256. |
| `scripts/validate.py` | Checks the catalog. It runs on every commit and push, and in CI. |
| `scripts/hash_files.py <folder>` | Writes each file's sha256 into the catalog. It never changes the hash of an approved track. |
| `scripts/export_credits.py` | Writes `out/credits.json` for the website's credits page. |
| `scripts/export_playlist.py` | Writes `out/<station>/<playlist>.m3u` for AzuraCast. |
| `scripts/check_media.py <folder>` | Checks that every audio file on the server outside `incoming/` is an approved track with a matching sha256. |
| [`docs/server-setup.md`](docs/server-setup.md) | Building the AzuraCast server from scratch. |
| [`docs/website.md`](docs/website.md) | How the station page and credits fit together. |
| [`LICENSES.md`](LICENSES.md) | The licences I accept, for music and spoken word. |
| [`DECISIONS.md`](DECISIONS.md) | What I decided, what I turned down, and why. |

Both export scripts write approved tracks only, and refuse to run on a catalog that fails
validation.

## 🎵 Adding a track

1. Download the original file and rename it to `<id>.<ext>`, e.g. `fma-0001.mp3`.
2. Add a row to `catalog/tracks.csv` with `status=pending`.
3. Save the source page and the licence page with the Wayback Machine and write
   `evidence/<id>.json`.
4. Upload the file to the station's `incoming/` folder, which isn't linked to any playlist, so
   nothing plays before it's approved. Run `hash_files.py` on the media folder.
5. Run `python3 scripts/validate.py`, review the track, and set `status=approved` and
   `reviewed_by`.
6. Move the file into its playlist folder (e.g. `lofi/`); AzuraCast adds it to that playlist.
   `check_media.py` confirms nothing unapproved is outside `incoming/`.
7. Commit on a branch off `dev` and open a PR into `dev`.

Run `bash scripts/install-hooks.sh` once after cloning. The hooks need `python3` and either Docker
or gitleaks 8.30.0, and they block secrets, home-network details and broken catalogs before
anything leaves my machine.

## 🎤 Artists: removing a track

If you're an artist and want a track taken off the air, email
[admin@audiobookmanager.com](mailto:admin@audiobookmanager.com) and I'll remove it.

## 📜 Licence

The scripts are GPL-3.0 (see [`LICENSE`](LICENSE)). The catalog data describes third-party works,
and each of those works stays under its own licence, listed in `catalog/tracks.csv`.

---

## ⚡ Support the Project

ABM Radio is part of [AudioBook Manager](https://audiobookmanager.com). If you find my work useful,
consider supporting development:

<p align="center">
  <a href="https://ko-fi.com/sunbrolynk">
    <img src="https://img.shields.io/badge/Ko--fi-Support%20Development-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi">
  </a>
  <a href="https://buymeacoffee.com/sunbrolynk">
    <img src="https://img.shields.io/badge/Buy%20Me%20A%20Monster-Support-FFDD00?style=for-the-badge&logo=data:image/svg%2Bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iYmxhY2siPjxwYXRoIGQ9Ik01IDJoMTRsLTEgMThINkw1IDJ6bTIgMmwuNzUgMTRoOC41TDE3IDRIN3oiLz48cGF0aCBkPSJNMTMgNmwtMyA1aDIuNUwxMSAxN2w1LTdoLTNsMi00aC0yeiIvPjxwYXRoIGQ9Ik04IDIwaDh2Mkg4di0yeiIvPjwvc3ZnPg%3D%3D" alt="Buy Me A Monster">
  </a>
</p>

<p align="center">
  <em>Support goes to AudioBook Manager's development. The stations themselves stay free and
  ad-free, and nothing on air is paid for.</em>
</p>

<p align="center">
  Made with ❤️ for audiobook lovers
</p>
