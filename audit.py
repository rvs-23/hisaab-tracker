"""Append-only audit trail of every data save.

Each successful save appends one JSON line to ``changes.jsonl`` in the data
folder recording exactly which rows were added and removed. Nothing in the
log is ever rewritten, so it is the complete edit history of the CSVs.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

CHANGES_LOG = "changes.jsonl"
_ROW_CAP = 100  # log full rows up to this many per side; beyond, just the count


def _row_multiset(df: pd.DataFrame, columns: list[str]) -> Counter:
    """Returns the frame's rows as a multiset of native-Python tuples.

    A multiset (rather than a set) keeps duplicate rows countable, so an edit
    that de-duplicates data still shows up as a removal.

    Args:
        df: Frame to convert; ``None`` or empty yields an empty Counter.
        columns: Canonical column order to compare in.
    """
    if df is None or df.empty:
        return Counter()
    rows = []
    for row in df.reindex(columns=columns).itertuples(index=False):
        vals = [None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in row]
        rows.append(tuple(vals))
    return Counter(rows)


def log_change(root: Path, filename: str, before: pd.DataFrame, after: pd.DataFrame,
               columns: list[str]) -> str | None:
    """Appends one JSON line describing what a save changed.

    The record carries ``ts``, ``file``, the ``[profile, year]`` pairs touched,
    ``rows_after`` (the file's row count after the write, a quick integrity
    check), and the exact rows ``added``/``removed`` (full rows up to 100 per
    side, else the count). A save that changed nothing logs nothing.

    A failure here never blocks or corrupts the write that already succeeded,
    but it is not silent either: the reason is returned so the caller can tell
    the user their change went through *unaudited*. Losing the audit trail
    without noticing is the failure mode this guards against.

    Args:
        root: Data folder that holds the log.
        filename: Name of the CSV that was written.
        before: Frame read from disk before the write (CSV-normalised).
        after: Frame read back after the write (CSV-normalised).
        columns: Canonical column order for the row comparison.

    Returns:
        ``None`` when the record was written (or there was nothing to record),
        else a short description of why the audit write failed.
    """
    try:
        bc, ac = _row_multiset(before, columns), _row_multiset(after, columns)
        added = [dict(zip(columns, r)) for r in (ac - bc).elements()]
        removed = [dict(zip(columns, r)) for r in (bc - ac).elements()]
        if not added and not removed:
            return None
        touched = sorted(
            {(d.get("profile"), int(d["year"])) for d in (added + removed) if d.get("year") is not None},
            key=lambda t: (str(t[0]), t[1]),
        )
        record = {
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "file": filename,
            "touched": [[p, y] for p, y in touched],
            "rows_after": int(len(after)),
            "added": added if len(added) <= _ROW_CAP else len(added),
            "removed": removed if len(removed) <= _ROW_CAP else len(removed),
        }
        with open(root / CHANGES_LOG, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return None
    except Exception as exc:  # noqa: BLE001 - the write already succeeded
        return f"{type(exc).__name__}: {exc}"


def last_entry(root: Path, profile_key: str) -> tuple[datetime, str] | None:
    """Returns when ``profile_key``'s data was last saved, and to which file.

    Scans the log newest-first. A record counts for a person if it touched
    their rows: its ``touched`` pairs, or the profile on any logged row
    (adjustment saves carry no year, so they never appear in ``touched``).

    Returns:
        ``(timestamp, filename)``, or ``None`` with no log or no matching record.
    """
    path = root / CHANGES_LOG
    if not path.exists():
        return None
    for line in reversed(path.read_text().splitlines()):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        people = {t[0] for t in rec.get("touched", [])}
        for side in ("added", "removed"):
            if isinstance(rec.get(side), list):
                people |= {r.get("profile") for r in rec[side]}
        if profile_key in people:
            return datetime.fromisoformat(rec["ts"]), rec["file"]
    return None


def row_last_changed(root: Path, filename: str, key_columns: list[str]) -> dict[tuple, datetime]:
    """When each row of ``filename`` last got a new amount, keyed by ``key_columns``.

    An edit logs the new row as added, so the latest record that added a key
    is its last change. A record that removed the same key with the same
    ``amount`` only touched its text, so it doesn't count. Rows saved before
    the audit log existed, or in a save too large to log row by row, are absent.
    """
    path = root / CHANGES_LOG
    if not path.exists():
        return {}
    stamps: dict[tuple, datetime] = {}
    for line in path.read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("file") != filename or not isinstance(rec.get("added"), list):
            continue
        ts = datetime.fromisoformat(rec["ts"])
        removed = rec.get("removed") if isinstance(rec.get("removed"), list) else []
        before = {tuple(r.get(k) for k in key_columns): r.get("amount") for r in removed}
        for row in rec["added"]:
            if all(k in row for k in key_columns):
                key = tuple(row[k] for k in key_columns)
                if key in before and before[key] == row.get("amount"):
                    continue
                stamps[key] = ts
    return stamps
