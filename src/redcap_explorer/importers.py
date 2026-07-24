"""Local file import and REDCap data-dictionary parsing."""
from __future__ import annotations
import csv
import hashlib
import io
from pathlib import Path
from typing import BinaryIO, Dict, Iterable, Union

import pandas as pd
from charset_normalizer import from_bytes

from .inference import infer_dataset_structure
from .schema import Dataset

Source = Union[str, Path, BinaryIO]


def _read_bytes(source: Source) -> tuple[bytes, str, Path | None]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        return path.read_bytes(), path.name, path
    raw = source.getvalue() if hasattr(source, "getvalue") else source.read()
    return raw, getattr(source, "name", "uploaded.csv"), None


def detect_encoding(raw: bytes) -> str:
    """Return a conservative encoding without transmitting file content."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    best = from_bytes(raw[:100_000]).best()
    return best.encoding if best and best.encoding else "utf-8"


def detect_delimiter(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:10_000], delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def load_dataset(source: Source) -> Dataset:
    raw, name, path = _read_bytes(source)
    encoding = detect_encoding(raw)
    suffix = Path(name).suffix.lower()
    if suffix == ".xlsx":
        data = pd.read_excel(io.BytesIO(raw), dtype_backend="numpy_nullable")
        delimiter = ""
    elif suffix == ".csv":
        text = raw.decode(encoding, errors="replace")
        delimiter = detect_delimiter(text)
        data = pd.read_csv(io.StringIO(text), sep=delimiter, low_memory=False)
    else:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")
    data.columns = [str(c).strip() for c in data.columns]
    structure, key = infer_dataset_structure(data)
    return Dataset(
        name=name, path=path, data=data, encoding=encoding, delimiter=delimiter,
        file_hash=hashlib.sha256(raw).hexdigest(),
        duplicate_rows=int(data.duplicated().sum()),
        empty_columns=[c for c in data if data[c].isna().all()],
        likely_instrument=_instrument_name(data, name), structure=structure,
        candidate_key=key,
    )


def _instrument_name(data: pd.DataFrame, filename: str) -> str:
    if "redcap_repeat_instrument" in data and data["redcap_repeat_instrument"].notna().any():
        modes = data["redcap_repeat_instrument"].dropna().astype(str).mode()
        if len(modes):
            return modes.iloc[0]
    return Path(filename).stem


def load_data_dictionary(source: Source) -> Dict[str, Dict[str, str]]:
    raw, _, _ = _read_bytes(source)
    enc = detect_encoding(raw)
    frame = pd.read_csv(io.StringIO(raw.decode(enc, errors="replace"))).fillna("")
    aliases = {str(c).strip().lower(): c for c in frame.columns}
    field_col = aliases.get("variable / field name") or aliases.get("field_name")
    if not field_col:
        raise ValueError("Data dictionary lacks a variable/field-name column")
    return {str(row[field_col]): {str(k): str(v) for k, v in row.items()} for _, row in frame.iterrows()}
