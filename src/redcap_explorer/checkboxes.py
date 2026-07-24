"""REDCap checkbox discovery and reshaping."""
from __future__ import annotations
import re
from typing import Dict, List
import pandas as pd
from .redcap_metadata import field_metadata


def checkbox_groups(columns: list[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for column in columns:
        match = re.match(r"^(.+)___([^_]+)$", column)
        if match:
            groups.setdefault(match.group(1), []).append(column)
    return groups


def transform_checkbox_group(df: pd.DataFrame, group: str, mode: str="separate", metadata: dict | None=None, delimiter: str=" | ") -> pd.DataFrame:
    columns = checkbox_groups(list(df.columns)).get(group, [])
    if not columns:
        raise ValueError(f"Checkbox group not found: {group}")
    if mode == "separate":
        return df.copy()
    labels = {c: (field_metadata(metadata or {}, c)["checkbox_label"] or c.rsplit("___", 1)[-1]) for c in columns}
    selected = df[columns].fillna(0).apply(pd.to_numeric, errors="coerce").eq(1)
    if mode in {"combined_codes", "combined_labels"}:
        values = [c.rsplit("___", 1)[-1] for c in columns] if mode == "combined_codes" else [labels[c] for c in columns]
        out = df.drop(columns=columns).copy()
        out[group] = selected.apply(lambda row: delimiter.join(values[i] for i, value in enumerate(row) if value), axis=1)
        return out
    if mode == "long":
        id_columns = [c for c in df.columns if c not in columns]
        frames=[]
        for column in columns:
            part=df[id_columns].copy(); part["checkbox_group"]=group
            part["checkbox_code"]=column.rsplit("___",1)[-1]; part["checkbox_label"]=labels[column]
            part["selected"]=selected[column].astype("int8"); frames.append(part)
        return pd.concat(frames, ignore_index=True)
    raise ValueError(f"Unsupported checkbox mode: {mode}")
