"""Safe, compact schema profiling."""
from __future__ import annotations
import re
import pandas as pd
from .inference import infer_type, ADMIN
from .stata_export import name_crosswalk
from .redcap_metadata import field_metadata


def profile_dataset(df: pd.DataFrame, source: str="", metadata: dict | None=None) -> pd.DataFrame:
    metadata=metadata or {}; cross=dict(zip(name_crosswalk(df).original_name,name_crosswalk(df).cleaned_name)); rows=[]
    for c in df:
        s=df[c]; typ=infer_type(s); non=s.dropna(); minimum=maximum=None
        if typ in {"integer","continuous"} and len(non): minimum,maximum=non.min(),non.max()
        elif typ in {"date","datetime"} and len(non):
            p=pd.to_datetime(non,errors="coerce"); minimum,maximum=p.min(),p.max()
        lname=c.lower(); role="administrative metadata" if lname in ADMIN or lname.endswith("_complete") else "identifier" if re.search(r"(^|_)id($|_)",lname) else typ
        md=field_metadata(metadata,c)
        if md["identifier"]: role="identifier"
        rows.append({"source_file":source,"original_name":c,"cleaned_name":cross[c],"variable_label":md["label"],"inferred_type":typ,"missing_pct":round(100*s.isna().mean(),1),"unique_values":int(s.nunique(dropna=True)),"minimum":minimum,"maximum":maximum,"sample":", ".join(non.astype(str).drop_duplicates().head(3).str.slice(0,50)),"role":role,"form_name":md["form_name"],"validation":md["validation"],"required":md["required"],"checkbox_group":md["field_name"] if md["checkbox_code"] else "","checkbox_label":md["checkbox_label"]})
    return pd.DataFrame(rows)


def shared_variables(datasets: list) -> pd.DataFrame:
    occurrences={}
    for ds in datasets:
        for c in ds.data: occurrences.setdefault(c.lower(),[]).append((ds,c))
    rows=[]
    for candidate, occ in occurrences.items():
        if len(occ)<2: continue
        sets=[set(ds.data[c].dropna().astype(str)) for ds,c in occ]; overlap=len(set.intersection(*sets))/max(1,len(set.union(*sets)))
        rows.append({"candidate":candidate,"files":", ".join(ds.name for ds,_ in occ),"original_names":", ".join(c for _,c in occ),"types":", ".join(infer_type(ds.data[c]) for ds,c in occ),"overlap_pct":round(100*overlap,1)})
    return pd.DataFrame(rows)
