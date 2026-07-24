"""Shared data structures used by the processing engine."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class VariableProfile:
    source_file: str
    original_name: str
    cleaned_name: str
    label: str = ""
    inferred_type: str = "string"
    missing_pct: float = 0.0
    unique_count: int = 0
    minimum: Any = None
    maximum: Any = None
    sample: List[str] = field(default_factory=list)
    role: str = ""


@dataclass
class Dataset:
    name: str
    path: Optional[Path]
    data: pd.DataFrame
    encoding: str = "utf-8"
    delimiter: str = ","
    file_hash: str = ""
    duplicate_rows: int = 0
    empty_columns: List[str] = field(default_factory=list)
    likely_instrument: str = ""
    structure: str = "unknown"
    candidate_key: List[str] = field(default_factory=list)
    metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)
