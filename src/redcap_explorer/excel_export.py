"""Excel workbook export."""
from __future__ import annotations
from pathlib import Path
from typing import Dict
import pandas as pd


def _sheet(name: str, used: set[str]) -> str:
    name="".join("_" if c in "[]:*?/\\" else c for c in name)[:31] or "data"
    base=name; i=2
    while name.lower() in {x.lower() for x in used}: name=(base[:27]+f"_{i}")[:31]; i+=1
    used.add(name); return name


def export_excel(datasets: Dict[str,pd.DataFrame], path: str | Path, dictionary: pd.DataFrame | None=None, crosswalk: pd.DataFrame | None=None, report: pd.DataFrame | None=None, linkage: pd.DataFrame | None=None) -> Path:
    path=Path(path); used=set()
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in datasets.items(): df.to_excel(writer, sheet_name=_sheet(name,used), index=False)
        for name, frame in [("Data dictionary",dictionary),("Variable crosswalk",crosswalk),("Processing report",report),("Linkage summary",linkage)]:
            if frame is not None: frame.to_excel(writer, sheet_name=_sheet(name,used), index=False)
    return path
