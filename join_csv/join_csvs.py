#!/usr/bin/env python3
"""
join_csvs.py — inner-join two CSVs on a shared key column.

No command-line arguments. Edit join_config.py (paths, key, columns), then:
    python join_csvs.py
"""
import csv
import sys
from pathlib import Path

import join_config as config

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def resolve(p):
    path = Path(p)
    return path if path.is_absolute() else _ROOT / path


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    left_path  = resolve(config.LEFT_CSV)
    right_path = resolve(config.RIGHT_CSV)
    out_path   = resolve(config.OUTPUT_CSV)
    key        = config.KEY

    left_rows  = load(left_path)
    right_rows = load(right_path)

    for name, rows in (("LEFT_CSV", left_rows), ("RIGHT_CSV", right_rows)):
        if rows and key not in rows[0]:
            sys.exit(f"error: KEY '{key}' not found in {name} columns: {list(rows[0].keys())}")

    left_cols  = config.LEFT_COLS  or [key]
    right_cols = config.RIGHT_COLS or [c for c in (right_rows[0].keys() if right_rows else []) if c != key]

    right_by_key = {}
    for row in right_rows:
        right_by_key.setdefault(row.get(key, ""), []).append(row)

    header = [c for c in left_cols if c != key] + right_cols
    written = 0

    with open(out_path, "w", encoding="utf-8", newline="") as out:
        w = csv.DictWriter(out, fieldnames=header)
        w.writeheader()
        for row in left_rows:
            for rrow in right_by_key.get(row.get(key, ""), []):
                w.writerow({c: row.get(c, "") for c in left_cols if c != key} |
                           {c: rrow.get(c, "") for c in right_cols})
                written += 1

    print(f"Joined {written} rows -> {out_path}")


if __name__ == "__main__":
    main()
