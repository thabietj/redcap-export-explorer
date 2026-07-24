"""Quality-control checks which never include row-level values."""
from __future__ import annotations
from typing import List, Dict
import pandas as pd


def validate_dataset(df: pd.DataFrame, keys: List[str] | None=None) -> List[Dict[str,str]]:
    findings=[]
    for c in df.columns:
        if df[c].isna().all(): findings.append({"severity":"warning","check":"all_missing","variable":c,"message":"Variable is entirely missing"})
        elif df[c].nunique(dropna=False)==1: findings.append({"severity":"information","check":"constant","variable":c,"message":"Variable is constant"})
    if keys:
        missing=[k for k in keys if k not in df]
        if missing: findings.append({"severity":"error","check":"missing_key","variable":", ".join(missing),"message":"Required linkage variable is missing"})
        else:
            n=int(df[keys].isna().any(axis=1).sum())
            d=int(df.duplicated(keys, keep=False).sum())
            if n: findings.append({"severity":"error","check":"missing_key_values","variable":", ".join(keys),"message":f"{n} rows have missing key values"})
            if d: findings.append({"severity":"warning","check":"duplicate_key","variable":", ".join(keys),"message":f"{d} rows belong to duplicated keys"})
    return findings
