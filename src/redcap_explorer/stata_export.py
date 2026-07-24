"""Stata export with deterministic valid names and companion commands."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, Iterable
import io
import pandas as pd
import numpy as np

RESERVED={"aggregate","array","boolean","byte","case","class","default","delete","do","double","else","end","float","for","if","in","int","long","matrix","new","null","return","short","static","string","this","true","using","while"}


def prepare_stata_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize pandas values to types accepted by Stata's writer.

    REDCap/Excel imports can produce object columns containing bytes, pandas
    missing sentinels, or mixed scalar types. Stata accepts text columns only
    when every non-missing value is a Python string. Nested objects are rejected
    explicitly because stringifying them would silently change data meaning.
    """
    out=df.copy()
    for column in out.columns:
        series=out[column]
        if isinstance(series.dtype,pd.DatetimeTZDtype):
            out[column]=series.dt.tz_convert("UTC").dt.tz_localize(None)
            continue
        if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype):
            nonmissing=series[series.notna()]
            nested=nonmissing.map(lambda value:isinstance(value,(list,dict,set,tuple,np.ndarray))).any()
            if nested:
                raise ValueError(f"Column `{column}` contains nested values that cannot be represented safely in Stata")
            if nonmissing.empty:
                out[column]=pd.Series(np.nan,index=series.index,dtype="float64")
                continue
            def normalize(value):
                if pd.isna(value): return None
                if isinstance(value,(bytes,bytearray,memoryview)): return bytes(value).decode("utf-8",errors="replace")
                return value if isinstance(value,str) else str(value)
            out[column]=series.map(normalize).astype(object)
    return out


def _stata_value_labels(df: pd.DataFrame, labels: Dict[str,Dict]) -> Dict[str,Dict]:
    """Keep value labels only for numeric Stata variables."""
    return {column:mapping for column,mapping in labels.items() if column in df and pd.api.types.is_numeric_dtype(df[column]) and all(isinstance(code,(int,float,np.integer,np.floating)) for code in mapping)}


def clean_stata_name(name: str, used: set[str] | None=None) -> str:
    used = used if used is not None else set()
    cleaned=re.sub(r"[^A-Za-z0-9_]", "_", str(name).strip())
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned): cleaned="_"+cleaned
    cleaned=cleaned[:32]
    if cleaned.lower() in RESERVED: cleaned=(cleaned[:29]+"_v")
    base=cleaned; i=2
    while cleaned.lower() in {u.lower() for u in used}:
        suffix=f"_{i}"; cleaned=base[:32-len(suffix)]+suffix; i+=1
    used.add(cleaned); return cleaned


def name_crosswalk(df: pd.DataFrame, source: str="") -> pd.DataFrame:
    used=set(); rows=[]
    for c in df.columns: rows.append({"source_file":source,"original_name":c,"cleaned_name":clean_stata_name(c,used)})
    return pd.DataFrame(rows)


def export_stata(df: pd.DataFrame, path: str | Path, variable_labels: Dict[str,str] | None=None, value_labels: Dict[str,Dict] | None=None, date_formats: Dict[str,str] | None=None, source_files: Iterable[str]=(), keys: list[str] | None=None) -> Path:
    path=Path(path); cross=name_crosswalk(df); renamed=df.rename(columns=dict(zip(cross.original_name,cross.cleaned_name))).copy()
    labels={dict(zip(cross.original_name,cross.cleaned_name)).get(k,k):v[:80] for k,v in (variable_labels or {}).items()}
    mapping=dict(zip(cross.original_name,cross.cleaned_name))
    values=_stata_value_labels(renamed,{mapping.get(k,k):v for k,v in (value_labels or {}).items() if mapping.get(k,k) in renamed})
    convert_dates={mapping.get(k,k):v for k,v in (date_formats or {}).items() if mapping.get(k,k) in renamed}
    renamed=prepare_stata_dataframe(renamed)
    renamed.to_stata(path, write_index=False, version=118, variable_labels=labels, value_labels=values, convert_dates=convert_dates)
    do=path.with_suffix(".do")
    key_clean=[dict(zip(cross.original_name,cross.cleaned_name)).get(k,k) for k in (keys or [])]
    lines=["* Generated locally by REDCap Export Explorer", *(f"* Source: {s}" for s in source_files), f'use "{path.name}", clear']
    if key_clean: lines += [f"isid {' '.join(key_clean)}", f"duplicates report {' '.join(key_clean)}"]
    lines += ["misstable summarize"]
    do.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return path


def export_stata_bytes(df: pd.DataFrame, variable_labels: Dict[str,str] | None=None, value_labels: Dict[str,Dict] | None=None, source_files: Iterable[str]=(), keys: list[str] | None=None) -> tuple[bytes,str,pd.DataFrame]:
    """Create an in-memory DTA and companion do-file without persisting clinical rows."""
    cross=name_crosswalk(df); mapping=dict(zip(cross.original_name,cross.cleaned_name))
    renamed=df.rename(columns=mapping).copy(); labels={mapping.get(k,k):v[:80] for k,v in (variable_labels or {}).items() if mapping.get(k,k) in renamed and v}
    values=_stata_value_labels(renamed,{mapping.get(k,k):v for k,v in (value_labels or {}).items() if mapping.get(k,k) in renamed})
    renamed=prepare_stata_dataframe(renamed)
    buffer=io.BytesIO(); renamed.to_stata(buffer,write_index=False,version=118,variable_labels=labels,value_labels=values)
    clean_keys=[mapping.get(k,k) for k in (keys or [])]
    lines=["* Generated locally by REDCap Export Explorer",*(f"* Source: {s}" for s in source_files),"* After extracting this archive:"]
    if clean_keys: lines += [f"isid {' '.join(clean_keys)}",f"duplicates report {' '.join(clean_keys)}"]
    lines += ["misstable summarize"]
    return buffer.getvalue(),"\n".join(lines)+"\n",cross
