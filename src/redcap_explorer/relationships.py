"""Relationship diagnostics and guarded merges."""
from __future__ import annotations
from typing import Dict, List
import pandas as pd


def analyze_relationship(left: pd.DataFrame, right: pd.DataFrame, left_keys: List[str], right_keys: List[str] | None = None) -> Dict:
    right_keys = right_keys or left_keys
    if len(left_keys) != len(right_keys) or not left_keys: raise ValueError("Select matching key columns")
    lu = not left.duplicated(left_keys).any(); ru = not right.duplicated(right_keys).any()
    relationship = "one-to-one" if lu and ru else "one-to-many" if lu else "many-to-one" if ru else "many-to-many"
    lk = set(map(tuple, left[left_keys].drop_duplicates().astype(str).to_numpy()))
    rk = set(map(tuple, right[right_keys].drop_duplicates().astype(str).to_numpy()))
    common = lk & rk
    expected = len(left.merge(right, left_on=left_keys, right_on=right_keys, how="outer"))
    return {"relationship": relationship, "left_unique": lu, "right_unique": ru,
            "left_duplicate_keys": int(left.duplicated(left_keys, keep=False).sum()), "right_duplicate_keys": int(right.duplicated(right_keys, keep=False).sum()),
            "matched_key_pct": round(100*len(common)/max(1,len(lk|rk)),1), "unmatched_left_keys": len(lk-rk), "unmatched_right_keys": len(rk-lk),
            "expected_rows": expected, "unsafe": relationship == "many-to-many"}


def safe_merge(left: pd.DataFrame, right: pd.DataFrame, keys: List[str], how: str="left", confirm_many_to_many: bool=False) -> pd.DataFrame:
    info = analyze_relationship(left, right, keys)
    if info["unsafe"] and not confirm_many_to_many:
        raise ValueError("Many-to-many merge blocked: add a secondary key, aggregate, keep linked tables, or explicitly confirm")
    validate = None if info["unsafe"] else info["relationship"].replace("-", "_")
    return left.merge(right, on=keys, how=how, validate=validate, suffixes=("", "_using"))
