from pathlib import Path
import pandas as pd
import pytest
import socket

from redcap_explorer.importers import load_dataset, detect_encoding
from redcap_explorer.inference import infer_type
from redcap_explorer.profiling import shared_variables
from redcap_explorer.identifiers import score_identifiers
from redcap_explorer.relationships import analyze_relationship, safe_merge
from redcap_explorer.stata_export import clean_stata_name, export_stata, export_stata_bytes, prepare_stata_dataframe
from redcap_explorer.excel_export import export_excel
from redcap_explorer.transformations import parse_date, map_missing, apply_transformations, convert_numeric
from redcap_explorer.config import ProjectConfig, save_project, load_project, schema_diff, project_to_bytes, project_from_bytes, metadata_diff, apply_schema_mapping
from redcap_explorer.importers import load_data_dictionary
from redcap_explorer.redcap_metadata import parse_choices, field_metadata, value_labels_for_columns
from redcap_explorer.checkboxes import checkbox_groups, transform_checkbox_group
from redcap_explorer.privacy import privacy_scan
from desktop_launcher import available_port

ROOT=Path(__file__).parents[1]
SYN=ROOT/"synthetic_data"

def test_import_encoding_and_structure():
    ds=load_dataset(SYN/"demographics.csv")
    assert len(ds.data)==5 and ds.structure=="one row per record"
    assert detect_encoding(b"a,b\n1,2\n").lower().replace("_","-") in {"ascii","utf-8","utf-8-sig"}

def test_inference_and_checkbox():
    assert infer_type(pd.Series([1,0,1],name="choice___1"))=="checkbox"
    assert infer_type(pd.Series([1,2,3],name="age"))=="integer"

def test_stata_name_cleaning_and_collision():
    used=set(); first=clean_stata_name("1 invalid name that is excessively long",used); second=clean_stata_name("1 invalid name that is excessively long",used)
    assert len(first)<=32 and first.startswith("_") and first!=second

def test_shared_and_identifier_score():
    datasets=[load_dataset(SYN/"demographics.csv"),load_dataset(SYN/"diagnoses.csv")]
    assert "record_id" in set(shared_variables(datasets).candidate)
    scores=score_identifiers(datasets); assert scores.iloc[0].candidate=="record_id"

def test_composite_relationship_and_many_many_guard():
    dx=load_dataset(SYN/"diagnoses.csv").data; meds=load_dataset(SYN/"medications.csv").data
    assert analyze_relationship(dx,meds,["record_id"])["relationship"]=="many-to-many"
    with pytest.raises(ValueError): safe_merge(dx,meds,["record_id"])
    d=dx.drop_duplicates(["record_id","redcap_repeat_instance"])
    assert analyze_relationship(d,d,["record_id","redcap_repeat_instance"])["left_unique"]

def test_dates_and_missing_mapping():
    out=parse_date(pd.Series(["31/12/2024"]),"%d/%m/%Y"); assert out.iloc[0].day==31
    with pytest.raises(ValueError): parse_date(pd.Series(["31/99/2024"]),"%d/%m/%Y")
    assert map_missing(pd.Series(["unknown","ok"]),["unknown"]).isna().iloc[0]

def test_exports(tmp_path):
    df=pd.DataFrame({"record_id":["S1"],"group":[1]})
    export_stata(df,tmp_path/"x.dta",keys=["record_id"])
    export_excel({"patients":df},tmp_path/"x.xlsx")
    assert (tmp_path/"x.dta").exists() and (tmp_path/"x.do").exists() and (tmp_path/"x.xlsx").exists()
    content,commands,cross=export_stata_bytes(df,{"group":"Group"},{"group":{1:"One"}},keys=["record_id"])
    assert content.startswith(b"<stata_dta>") and "isid record_id" in commands and len(cross)==2

def test_stata_export_normalizes_real_world_mixed_text_and_bytes():
    df=pd.DataFrame({"record_id":["S1","S2","S3"],"mixed":[b"plain bytes",42,None],"empty":[None,None,None]})
    prepared=prepare_stata_dataframe(df)
    assert prepared.mixed.tolist()==["plain bytes","42",None] and prepared["empty"].isna().all()
    content,_,_=export_stata_bytes(df,keys=["record_id"])
    assert content.startswith(b"<stata_dta>")
    with pytest.raises(ValueError,match="nested values"):
        prepare_stata_dataframe(pd.DataFrame({"bad":[{"a":1}]}))
    string_codes=pd.DataFrame({"diagnosis_code":["D001","D002"]})
    content,_,_=export_stata_bytes(string_codes,value_labels={"diagnosis_code":{"D001":"Condition A"}})
    assert content.startswith(b"<stata_dta>")

def test_project_roundtrip_and_schema_diff(tmp_path):
    c=ProjectConfig(selected_variables={"a.csv":["id"]}); p=save_project(c,tmp_path/"p.yaml")
    assert load_project(p).selected_variables==c.selected_variables
    diff=schema_diff({"id":"string","old":"int"},{"id":"int","new":"str"},["id","key"])
    assert diff["removed"]==["old"] and diff["missing_required"]==["key"] and "id" in diff["changed_types"]
    assert project_from_bytes(project_to_bytes(c)).selected_variables==c.selected_variables

def test_redcap_metadata_and_value_labels():
    metadata=load_data_dictionary(SYN/"redcap_data_dictionary.csv")
    assert parse_choices("1, Yes | 0, No")=={"1":"Yes","0":"No"}
    assert field_metadata(metadata,"race___2")["checkbox_label"]=="Group B"
    assert value_labels_for_columns(metadata,["sex"])["sex"]=={1:"Male",2:"Female"}
    changed={**metadata,"sex":{**metadata["sex"],"Field Label":"Reported sex"}}
    assert "sex" in metadata_diff(metadata,changed)["changed_labels"]

def test_checkbox_export_modes():
    df=pd.DataFrame({"id":[1,2],"choice___1":[1,0],"choice___2":[0,1]})
    assert checkbox_groups(list(df))=={"choice":["choice___1","choice___2"]}
    combined=transform_checkbox_group(df,"choice","combined_codes")
    assert list(combined.choice)==["1","2"]
    long=transform_checkbox_group(df,"choice","long")
    assert len(long)==4 and set(long.selected)=={0,1}

def test_phase_three_transformations_are_strict_and_reproducible():
    df=pd.DataFrame({"id":[1,1,2],"text":[" A "," A ","B"],"dob":["2000-01-01"]*3,"visit":["2020-01-01","2020-01-01","2021-01-01"],"a":[1,1,0],"b":[1,1,1]})
    operations=[{"type":"trim","column":"text"},{"type":"case","column":"text","mode":"lower"},{"type":"derive_age","column":"dob","reference_column":"visit","new_name":"age"},{"type":"row_count","columns":["a","b"],"new_name":"total"},{"type":"remove_duplicates","columns":["id","visit"]}]
    out=apply_transformations(df,operations)
    assert list(out.text)==["a","b"] and list(out.total)==[2,1] and out.age.notna().all()
    with pytest.raises(Exception): apply_transformations(df,[{"type":"change_type","column":"text","target":"integer"}])

def test_localized_numeric_conversion_missing_tokens_and_invalid_policy():
    comma=pd.Series(["1,25","2 000,50","NAN",""],name="result")
    out=convert_numeric(comma,"float",decimal_separator=",",thousands_separator=" ")
    assert out.iloc[0]==1.25 and out.iloc[1]==2000.5 and out.iloc[2:].isna().all()
    dot=pd.Series(["1,234.5","bad"],name="result")
    with pytest.raises(ValueError,match="1 value"):
        convert_numeric(dot,"float",decimal_separator=".",thousands_separator=",")
    tolerated=convert_numeric(dot,"float",decimal_separator=".",thousands_separator=",",invalid_policy="set_missing")
    assert tolerated.iloc[0]==1234.5 and pd.isna(tolerated.iloc[1])
    with pytest.raises(ValueError,match="Decimal and thousands"):
        convert_numeric(pd.Series(["1,2"]),"float",",",",")

def test_schema_mapping_updates_keys_selections_and_recipe():
    config=ProjectConfig(selected_variables={"x.csv":["old","value"]},linkage_keys={"x.csv":["old"]},transformations=[{"dataset":"x.csv","type":"trim","column":"old"}])
    mapped=apply_schema_mapping(config,{"x.csv":{"old":"new"}})
    assert mapped.selected_variables["x.csv"]==["new","value"] and mapped.linkage_keys["x.csv"]==["new"] and mapped.transformations[0]["column"]=="new"

def test_extended_privacy_scan_reports_fields_not_values():
    flags=privacy_scan(pd.DataFrame({"contact":["+27 82 123 4567","+27 83 987 6543"],"clinical_notes":["x"*140,"y"*150]}))
    assert set(flags.variable)=={"contact","clinical_notes"}
    assert not any("4567" in str(value) for value in flags.to_numpy().flat)

def test_no_network_calls_in_runtime_source():
    text="\n".join(p.read_text() for p in (ROOT/"src"/"redcap_explorer").glob("*.py"))
    forbidden=["requests.","httpx.","urllib.request","socket.create_connection","telemetry","analytics"]
    assert not any(token in text for token in forbidden)

def test_streamlit_widgets_are_not_created_inside_dataset_lookup_generators():
    app=(ROOT/"app.py").read_text()
    assert "next(d for d in datasets if d.name==st.selectbox" not in app
    assert 'key="relationship-left"' in app and 'key="relationship-right"' in app

def test_desktop_launcher_selects_an_available_local_port(monkeypatch):
    class Probe:
        def __enter__(self): return self
        def __exit__(self,*args): return None
        def bind(self,address): assert address==("127.0.0.1",0)
        def getsockname(self): return ("127.0.0.1",54321)
    monkeypatch.setattr("desktop_launcher.socket.socket",lambda *args:Probe())
    assert available_port()=="54321"
