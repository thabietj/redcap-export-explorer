"""Variable and dataset grain inference."""
from __future__ import annotations
import re
from typing import Tuple, List
import pandas as pd

ADMIN = {"redcap_event_name", "redcap_repeat_instrument", "redcap_repeat_instance"}


def infer_type(series: pd.Series) -> str:
    nonnull = series.dropna()
    name = str(series.name).lower()
    if re.search(r"___[^_]+$", name): return "checkbox"
    if not len(nonnull): return "empty"
    if pd.api.types.is_bool_dtype(series): return "binary"
    if pd.api.types.is_numeric_dtype(series):
        unique = nonnull.nunique()
        if unique <= 2: return "binary"
        return "integer" if (nonnull.astype(float) % 1 == 0).all() else "continuous"
    text = nonnull.astype(str).str.strip()
    if text.nunique() <= 2: return "binary"
    date_hint = bool(re.search(r"date|dob|time", name))
    if date_hint:
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=False)
        if parsed.notna().mean() >= .8:
            return "datetime" if text.str.contains(r"\d:\d").any() else "date"
    if text.str.len().median() > 80 or text.str.contains(r"\s").mean() > .7 and text.str.len().mean() > 35:
        return "free text"
    return "categorical" if text.nunique() <= min(30, max(10, len(text) // 3)) else "string"


def infer_dataset_structure(df: pd.DataFrame) -> Tuple[str, List[str]]:
    cols = set(df.columns)
    rid = next((c for c in df.columns if c.lower() in {"record_id","recordid","patient_id","participant_id","study_id"}), None)
    if "redcap_repeat_instrument" in cols and df["redcap_repeat_instrument"].notna().any():
        key = [c for c in [rid, "redcap_repeat_instrument", "redcap_repeat_instance"] if c]
        return "repeating instrument", key
    if "redcap_event_name" in cols:
        return "longitudinal", [c for c in [rid, "redcap_event_name"] if c]
    if rid and df[rid].duplicated().any():
        lower = " ".join(str(c).lower() for c in df.columns)
        for token, grain in [("lab test specimen", "laboratory-level"), ("medication drug dose", "medication-level"), ("diagnos", "diagnosis-level"), ("visit encounter", "encounter-level")]:
            if any(t in lower for t in token.split()): return grain, [rid]
        return "event-level", [rid]
    return ("one row per record", [rid]) if rid else ("unknown", [])
