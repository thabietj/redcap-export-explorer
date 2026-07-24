"""Non-mutating data transformations."""
from __future__ import annotations
import pandas as pd

DEFAULT_NUMERIC_MISSING=["NA","N/A","NAN","NULL","NONE","MISSING","UNKNOWN","NOT KNOWN","NOT APPLICABLE","NOT DONE","REFUSED",""]


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing=[c for c in columns if c not in df]
    if missing: raise ValueError(f"Transformation requires missing column(s): {', '.join(missing)}")


def convert_numeric(series: pd.Series, target: str, decimal_separator: str=".", thousands_separator: str="", missing_values: list[str] | None=None, invalid_policy: str="block") -> pd.Series:
    """Convert localized numeric text using explicit, reproducible rules."""
    if decimal_separator not in {".",","}: raise ValueError("Decimal separator must be a full stop or comma")
    if thousands_separator and thousands_separator==decimal_separator: raise ValueError("Decimal and thousands separators must be different")
    tokens={str(value).strip().casefold() for value in (missing_values if missing_values is not None else DEFAULT_NUMERIC_MISSING)}
    text=series.astype("string").str.strip()
    text=text.mask(text.str.casefold().isin(tokens),pd.NA)
    if thousands_separator: text=text.str.replace(thousands_separator,"",regex=False)
    if decimal_separator==",": text=text.str.replace(",",".",regex=False)
    converted=pd.to_numeric(text,errors="coerce")
    invalid=text.notna() & converted.isna()
    if target=="integer":
        fractional=converted.notna() & converted.mod(1).ne(0)
        invalid=invalid|fractional
        converted=converted.mask(fractional)
    if invalid.any() and invalid_policy=="block":
        raise ValueError(f"{int(invalid.sum())} value(s) in `{series.name}` are not valid {target} values. Add missing-value tokens, choose the correct separators, or allow invalid values to become missing.")
    if invalid_policy not in {"block","set_missing"}: raise ValueError(f"Unsupported invalid-value policy: {invalid_policy}")
    return converted.astype("Int64" if target=="integer" else "Float64")


def apply_transformations(df: pd.DataFrame, operations: list[dict]) -> pd.DataFrame:
    out = df.copy()
    for op in operations:
        kind, col = op["type"], op.get("column")
        if col: _require_columns(out,[col])
        if kind == "rename":
            if op["new_name"] in out and op["new_name"] != col: raise ValueError(f"Rename target already exists: {op['new_name']}")
            out = out.rename(columns={col: op["new_name"]})
        elif kind == "trim": out[col] = out[col].astype("string").str.strip()
        elif kind == "case":
            mode=op.get("mode", "lower")
            if mode not in {"lower","upper","title"}: raise ValueError(f"Unsupported case mode: {mode}")
            out[col] = getattr(out[col].astype("string").str, mode)()
        elif kind == "replace": out[col] = out[col].replace(op["mapping"])
        elif kind == "remove_duplicates": out = out.drop_duplicates(subset=op.get("columns"))
        elif kind == "date_part": out[op["new_name"]] = getattr(pd.to_datetime(out[col], errors="raise").dt, op["part"])
        elif kind == "binary_indicator": out[op["new_name"]] = out[col].isin(op.get("values",[])).astype("int8")
        elif kind == "row_count":
            columns=op["columns"]; _require_columns(out,columns)
            out[op["new_name"]]=out[columns].fillna(0).apply(pd.to_numeric,errors="raise").sum(axis=1)
        elif kind == "derive_age":
            reference=op.get("reference_column"); _require_columns(out,[reference])
            birth=pd.to_datetime(out[col],errors="raise"); ref=pd.to_datetime(out[reference],errors="raise")
            out[op["new_name"]]=((ref-birth).dt.days/365.2425).astype("Float64").round(1)
        elif kind == "change_type":
            target=op["target"]
            if target=="string": out[col]=out[col].astype("string")
            elif target in {"integer","float"}:
                out[col]=convert_numeric(out[col],target,op.get("decimal_separator","."),op.get("thousands_separator",""),op.get("missing_values"),op.get("invalid_policy","block"))
            elif target in {"date","datetime"}: out[col]=pd.to_datetime(out[col],format=op.get("format"),errors="raise")
            else: raise ValueError(f"Unsupported target type: {target}")
        elif kind == "aggregate":
            group_by=op["group_by"]; _require_columns(out,group_by+list(op["aggregations"]))
            out=out.groupby(group_by,dropna=False,as_index=False).agg(op["aggregations"])
        elif kind == "pivot_longer":
            value_columns=op["value_columns"]; _require_columns(out,op["id_columns"]+value_columns)
            out=out.melt(id_vars=op["id_columns"],value_vars=value_columns,var_name=op.get("names_to","variable"),value_name=op.get("values_to","value"))
        elif kind == "pivot_wider":
            _require_columns(out,op["index"]+[op["names_from"],op["values_from"]])
            out=out.pivot_table(index=op["index"],columns=op["names_from"],values=op["values_from"],aggfunc=op.get("aggfunc","first")).reset_index()
            out.columns=[str(c) for c in out.columns]
        else: raise ValueError(f"Unsupported transformation: {kind}")
    return out


def parse_date(series: pd.Series, date_format: str) -> pd.Series:
    """Parse an explicitly selected format; invalid values raise."""
    return pd.to_datetime(series, format=date_format, errors="raise")


def map_missing(series: pd.Series, values: list[str]) -> pd.Series:
    return series.replace(values, pd.NA)
