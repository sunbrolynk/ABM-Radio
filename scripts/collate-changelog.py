"""Folds the changelog.d fragments into CHANGELOG.md's [Unreleased] section at release time.

Each fragment is changelog.d/<slug>.<section>.md, holding one bullet exactly as it should read in
the changelog. Bullets land under their section's heading after the ones already there, in file
name order. --dry-run prints the result; otherwise CHANGELOG.md is written and the folded
fragments deleted.

Usage: python3 scripts/collate-changelog.py [--dry-run]
"""

# Python Imports
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
FRAGMENTS = ROOT / "changelog.d"
# Keep a Changelog's order, without Deprecated, which this project doesn't use.
SECTIONS = {"added": "Added", "changed": "Changed", "removed": "Removed", "fixed": "Fixed", "security": "Security"}
UNRELEASED = "## [Unreleased]"


def read_fragments(folder: Path) -> tuple[list[Path], dict[str, list[str]], list[str]]:
    paths = sorted(folder.glob("*.md"))
    bullets: dict[str, list[str]] = {}
    problems = []
    for path in paths:
        parts = path.name.split(".")
        if len(parts) != 3 or not parts[0] or parts[1] not in SECTIONS:
            problems.append(f"{path.name}: name must be <slug>.<{'|'.join(SECTIONS)}>.md")
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text.startswith("- "):
            problems.append(f"{path.name}: must hold one bullet starting '- '")
            continue
        bullets.setdefault(SECTIONS[parts[1]], []).append(text)
    return paths, bullets, problems


def collate(changelog: str, bullets: dict[str, list[str]]) -> str:
    lines = changelog.split("\n")
    if UNRELEASED not in lines:
        raise ValueError(f"CHANGELOG.md has no '{UNRELEASED}' heading")
    start = lines.index(UNRELEASED) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))

    # Split [Unreleased] into the text before any heading and each ### section's body.
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current = preamble
    for line in lines[start:end]:
        if line.startswith("### "):
            current = sections.setdefault(line[4:].strip(), [])
        else:
            current.append(line)

    for name, new in bullets.items():
        body = "\n".join(sections.get(name, [])).strip()
        sections[name] = "\n\n".join([body, *new] if body else new).split("\n")

    # Known sections in their standard order, then any others where they were.
    order = [s for s in SECTIONS.values() if s in sections] + [s for s in sections if s not in SECTIONS.values()]
    block = ["\n".join(preamble).strip()]
    block += [f"### {name}\n\n" + "\n".join(sections[name]).strip() for name in order]
    middle = "\n\n".join(b for b in block if b)
    tail = "\n".join(lines[end:])
    return "\n".join(lines[:start]) + "\n\n" + middle + ("\n\n" + tail if tail.strip() else "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the new CHANGELOG.md and change nothing")
    args = parser.parse_args()

    paths, bullets, problems = read_fragments(FRAGMENTS)
    if problems:
        for problem in problems:
            print(f"  ! {problem}", file=sys.stderr)
        return 1
    if not paths:
        print("  no fragments to fold")
        return 0
    try:
        result = collate(CHANGELOG.read_text(encoding="utf-8"), bullets)
    except ValueError as err:
        print(f"  ! {err}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(result, end="")
        return 0
    CHANGELOG.write_text(result, encoding="utf-8")
    for path in paths:
        path.unlink()
    print(f"  folded {len(paths)} fragment(s) into CHANGELOG.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
