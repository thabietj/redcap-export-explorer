"""De-identified processing manifests and HTML reports."""
from __future__ import annotations
import html, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from . import __version__
from .schema import Dataset


def build_manifest(datasets: List[Dataset], **details: Any) -> Dict[str,Any]:
    return {"generated_at":datetime.now(timezone.utc).isoformat(), "application_version":__version__,
      "inputs":[{"filename":d.name,"sha256":d.file_hash,"rows":len(d.data),"columns":len(d.data.columns),"structure":d.structure,"candidate_key":d.candidate_key} for d in datasets], **details}


def write_report(manifest: Dict[str,Any], directory: str | Path, stem: str="processing_report") -> tuple[Path,Path]:
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    jp=directory/f"{stem}.json"; hp=directory/f"{stem}.html"
    jp.write_text(json.dumps(manifest,indent=2,default=str),encoding="utf-8")
    sections=[]
    for k,v in manifest.items(): sections.append(f"<h2>{html.escape(str(k).replace('_',' ').title())}</h2><pre>{html.escape(json.dumps(v,indent=2,default=str))}</pre>")
    hp.write_text("<!doctype html><meta charset='utf-8'><title>REDCap Export Explorer report</title><style>body{font:15px system-ui;max-width:1000px;margin:3rem auto;padding:0 1rem}pre{white-space:pre-wrap;background:#f5f7f9;padding:1rem}</style><h1>Processing report</h1>"+"".join(sections),encoding="utf-8")
    return hp,jp
