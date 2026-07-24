"""Validated saved-project configuration and schema comparison."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Any
from pydantic import BaseModel, Field
import yaml
from .inference import infer_type


class ProjectConfig(BaseModel):
    version: str="2"
    sources: List[Dict[str,Any]]=Field(default_factory=list)
    selected_variables: Dict[str,List[str]]=Field(default_factory=dict)
    renames: Dict[str,str]=Field(default_factory=dict)
    type_conversions: Dict[str,str]=Field(default_factory=dict)
    linkage_keys: Dict[str,List[str]]=Field(default_factory=dict)
    relationships: List[Dict[str,Any]]=Field(default_factory=list)
    missing_value_rules: Dict[str,Any]=Field(default_factory=dict)
    transformations: List[Dict[str,Any]]=Field(default_factory=list)
    output_settings: Dict[str,Any]=Field(default_factory=dict)
    schemas: Dict[str,Dict[str,str]]=Field(default_factory=dict)
    metadata_snapshot: Dict[str,Dict[str,Any]]=Field(default_factory=dict)
    checkbox_modes: Dict[str,str]=Field(default_factory=dict)
    structure_overrides: Dict[str,str]=Field(default_factory=dict)
    date_formats: Dict[str,str]=Field(default_factory=dict)


def save_project(config: ProjectConfig, path: str | Path) -> Path:
    path=Path(path); data=config.model_dump()
    path.write_text(yaml.safe_dump(data,sort_keys=False) if path.suffix.lower() in {".yaml",".yml"} else json.dumps(data,indent=2),encoding="utf-8"); return path


def load_project(path: str | Path) -> ProjectConfig:
    path=Path(path); text=path.read_text(encoding="utf-8")
    return ProjectConfig.model_validate(yaml.safe_load(text) if path.suffix.lower() in {".yaml",".yml"} else json.loads(text))


def project_to_bytes(config: ProjectConfig, format: str="json") -> bytes:
    data=config.model_dump()
    text=yaml.safe_dump(data,sort_keys=False) if format.lower() in {"yaml","yml"} else json.dumps(data,indent=2)
    return text.encode("utf-8")


def project_from_bytes(content: bytes, filename: str="project.json") -> ProjectConfig:
    text=content.decode("utf-8")
    data=yaml.safe_load(text) if Path(filename).suffix.lower() in {".yaml",".yml"} else json.loads(text)
    return ProjectConfig.model_validate(data)


def dataset_schema(df) -> Dict[str,str]:
    return {str(column):infer_type(df[column]) for column in df.columns}


def schema_diff(old: Dict[str,str], new: Dict[str,str], required: List[str] | None=None) -> Dict[str,Any]:
    required=required or []; added=sorted(set(new)-set(old)); removed=sorted(set(old)-set(new))
    return {"added":added,"removed":removed,"changed_types":{k:{"old":old[k],"new":new[k]} for k in old.keys()&new.keys() if old[k]!=new[k]},"missing_required":sorted(set(required)-set(new))}


def compare_project_schemas(config: ProjectConfig, datasets: list) -> Dict[str,Any]:
    current={d.name:dataset_schema(d.data) for d in datasets}; result={}
    for name in sorted(set(config.schemas)|set(current)):
        required=config.selected_variables.get(name,[])+config.linkage_keys.get(name,[])
        result[name]=schema_diff(config.schemas.get(name,{}),current.get(name,{}),required)
    return result


def metadata_diff(old: Dict[str,Dict[str,Any]], new: Dict[str,Dict[str,Any]]) -> Dict[str,Any]:
    """Compare REDCap labels and choice definitions without examining row values."""
    from .redcap_metadata import field_metadata
    old_fields=set(old); new_fields=set(new); labels={}; choices={}
    for field in old_fields & new_fields:
        before=field_metadata(old,field); after=field_metadata(new,field)
        if before["label"] != after["label"]: labels[field]={"old":before["label"],"new":after["label"]}
        if before["choices"] != after["choices"]: choices[field]={"old":before["choices"],"new":after["choices"]}
    return {"added_fields":sorted(new_fields-old_fields),"removed_fields":sorted(old_fields-new_fields),"changed_labels":labels,"changed_choices":choices}


def apply_schema_mapping(config: ProjectConfig, mappings: Dict[str,Dict[str,str]]) -> ProjectConfig:
    """Return a project updated with user-confirmed old-to-new variable names."""
    data=config.model_dump()
    for filename,mapping in mappings.items():
        data["selected_variables"][filename]=[mapping.get(c,c) for c in data["selected_variables"].get(filename,[])]
        data["linkage_keys"][filename]=[mapping.get(c,c) for c in data["linkage_keys"].get(filename,[])]
        for op in data["transformations"]:
            if op.get("dataset")!=filename: continue
            for key in ["column","reference_column"]:
                if op.get(key) in mapping: op[key]=mapping[op[key]]
            for key in ["columns","group_by","id_columns","value_columns"]:
                if key in op: op[key]=[mapping.get(c,c) for c in op[key]]
    return ProjectConfig.model_validate(data)
