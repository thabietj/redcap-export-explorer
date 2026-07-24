"""Transparent identifier candidate scoring."""
from __future__ import annotations
import re
from typing import Dict, List
import pandas as pd
from .schema import Dataset


def score_identifiers(datasets: List[Dataset]) -> pd.DataFrame:
    groups: Dict[str, list] = {}
    for ds in datasets:
        for c in ds.data.columns: groups.setdefault(c.lower(), []).append((ds, c))
    rows = []
    for canonical, occurrences in groups.items():
        name_points = 30 if re.search(r"(^|_)(record|patient|participant|study|subject|folder)?_?id($|_)", canonical) else 0
        missing = sum(float(ds.data[c].isna().mean()) for ds,c in occurrences) / len(occurrences)
        unique = sum(float(ds.data[c].nunique(dropna=True) / max(1, ds.data[c].notna().sum())) for ds,c in occurrences) / len(occurrences)
        coverage = len(occurrences) / len(datasets)
        overlap = _overlap(occurrences)
        score = round(min(100, name_points + 25*(1-missing) + 20*unique + 15*coverage + 10*overlap))
        reasons = [f"Present in {len(occurrences)} of {len(datasets)} files", f"{missing:.1%} average missing", f"{unique:.1%} average uniqueness"]
        if len(occurrences)>1: reasons.append(f"{overlap:.1%} value overlap")
        if name_points: reasons.append("Identifier-like variable name")
        rows.append({"candidate": canonical, "files": ", ".join(ds.name for ds,_ in occurrences), "identifier_score": score, "overlap_pct": round(100*overlap,1), "reasons": "; ".join(reasons)})
    return pd.DataFrame(rows).sort_values("identifier_score", ascending=False, ignore_index=True)


def _overlap(occurrences: list) -> float:
    if len(occurrences) < 2: return 0.0
    sets = [set(ds.data[c].dropna().astype(str)) for ds,c in occurrences]
    union = set.union(*sets)
    return len(set.intersection(*sets)) / max(1, len(union))
