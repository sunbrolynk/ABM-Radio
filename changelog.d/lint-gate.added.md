- **Lint gate:** ruff now checks `scripts/` and `tests/` in the pre-commit and pre-push hooks and in
  CI, with its rule set pinned in `pyproject.toml` and the binary installed from the hash-pinned
  `requirements-tooling.lock` by `scripts/setup-tooling.sh`, so I run the same ruff everywhere.
