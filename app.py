"""Streamlit interface for REDCap Export Explorer."""
from __future__ import annotations
import io, json, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import streamlit as st
from redcap_explorer.importers import load_dataset, load_data_dictionary
from redcap_explorer.identifiers import score_identifiers
from redcap_explorer.profiling import profile_dataset, shared_variables
from redcap_explorer.privacy import privacy_scan
from redcap_explorer.relationships import analyze_relationship, safe_merge
from redcap_explorer.validation import validate_dataset
from redcap_explorer.stata_export import name_crosswalk, export_stata_bytes
from redcap_explorer.reporting import build_manifest
from redcap_explorer.config import ProjectConfig, project_from_bytes, project_to_bytes, dataset_schema, compare_project_schemas, metadata_diff
from redcap_explorer.checkboxes import checkbox_groups, transform_checkbox_group
from redcap_explorer.redcap_metadata import field_metadata, value_labels_for_columns
from redcap_explorer.transformations import apply_transformations
from redcap_explorer.config import apply_schema_mapping

st.set_page_config(page_title="REDCap Export Explorer", page_icon="🔒", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.8rem;max-width:1280px}.stAlert{border-radius:12px}
[data-testid="stSidebar"]{background:#f6f8fb}.step-note{color:#536471;font-size:.92rem}
.metric-card{border:1px solid #e2e8f0;border-radius:12px;padding:14px;background:white}
</style>""",unsafe_allow_html=True)
st.title("REDCap Export Explorer")
st.success("🔒 All processing occurs locally. No data are transmitted externally.")
st.caption("Files remain in memory unless you explicitly download an output or save a project. Previews are deliberately small.")

STEPS=["1 · Add data","2 · Understand data","3 · Find shared fields","4 · Link datasets","5 · Choose fields","6 · Prepare data","7 · Check quality","8 · Download"]
step=st.sidebar.radio("Your workflow", STEPS)
st.sidebar.progress((STEPS.index(step)+1)/len(STEPS),text=f"Step {STEPS.index(step)+1} of {len(STEPS)}")
with st.sidebar.expander("Files",expanded=step.startswith("1")):
    uploads=st.file_uploader("Data exports", type=["csv","xlsx"], accept_multiple_files=True,help="Select one or more REDCap CSV or Excel exports.")
    dictionary_upload=st.file_uploader("Data dictionary (optional)", type=["csv"],help="Adds labels, choices and validation metadata.")
    project_upload=st.file_uploader("Saved project (optional)", type=["json","yaml","yml"],help="Reapply decisions from an earlier export.")

@st.cache_data(show_spinner=False)
def parse_upload(name: str, content: bytes):
    f=io.BytesIO(content); f.name=name; return load_dataset(f)

datasets=[parse_upload(f.name,f.getvalue()) for f in uploads]
datasets_by_name={d.name:d for d in datasets}
if len(datasets_by_name)!=len(datasets):
    st.error("Two uploaded files have the same filename. Rename one file so every dataset has a unique name, then upload again.")
    st.stop()
project=None
if project_upload:
    try: project=project_from_bytes(project_upload.getvalue(),project_upload.name)
    except Exception as exc: st.sidebar.error(f"Project could not be loaded: {exc}")
if st.session_state.get("remapped_project") is not None and project_upload:
    project=ProjectConfig.model_validate(st.session_state["remapped_project"])
metadata={}
if dictionary_upload:
    f=io.BytesIO(dictionary_upload.getvalue()); f.name=dictionary_upload.name
    metadata=load_data_dictionary(f)
    for ds in datasets: ds.metadata=metadata

metadata_changes=metadata_diff(project.metadata_snapshot,metadata) if project and project.metadata_snapshot and metadata else {}

if not datasets:
    st.info("Start by opening **Files** in the sidebar and selecting one or more exports. For a safe demonstration, use the fictional files in `synthetic_data/`.")
    st.stop()

if project:
    differences=compare_project_schemas(project,datasets)
    blocking={name:diff for name,diff in differences.items() if diff["missing_required"]}
    changed={name:diff for name,diff in differences.items() if any(diff[k] for k in ["added","removed","changed_types","missing_required"])}
    if blocking: st.error("Saved-project variables or linkage keys are missing. Export is blocked until the schema differences are resolved.")
    elif changed: st.warning("The imported exports differ from the saved project. Review the schema report before export.")
    st.session_state["schema_blocking"]=bool(blocking)

if step.startswith("1"):
    st.subheader("Your data files")
    st.caption("Confirm that each file has the expected size and structure. You can correct the inferred structure below.")
    st.dataframe(pd.DataFrame([{"file":d.name,"rows":len(d.data),"columns":len(d.data.columns),"encoding":d.encoding,"delimiter":d.delimiter or "Excel","duplicate_rows":d.duplicate_rows,"empty_columns":len(d.empty_columns),"likely_instrument":d.likely_instrument,"inferred_structure":d.structure,"candidate_key":" + ".join(d.candidate_key)} for d in datasets]),hide_index=True,use_container_width=True)
    st.subheader("Dataset structure confirmation")
    structure_options=["one row per record","longitudinal","repeating instrument","event-level","encounter-level","laboratory-level","medication-level","diagnosis-level","unknown"]
    for d in datasets:
        default=(project.structure_overrides.get(d.name) if project else None) or d.structure
        d.structure=st.selectbox(d.name,structure_options,index=structure_options.index(default) if default in structure_options else len(structure_options)-1,key=f"structure-{d.name}")
    if project and changed:
        with st.expander("Schema-difference report",expanded=True): st.json(changed)
        if blocking:
            st.markdown("#### Resolve missing fields")
            st.caption("Map each field from the saved project to its replacement in the new export. Nothing is changed until you confirm.")
            mappings={}; unresolved=False
            for filename,diff in blocking.items():
                current=next((d for d in datasets if d.name==filename),None)
                if not current: st.error(f"The entire file `{filename}` is missing."); unresolved=True; continue
                mappings[filename]={}
                for old in diff["missing_required"]:
                    choice=st.selectbox(f"{filename}: replace `{old}` with",["— Select replacement —"]+list(current.data.columns),key=f"map-{filename}-{old}")
                    if choice.startswith("—"): unresolved=True
                    else: mappings[filename][old]=choice
            if st.button("Apply field mappings",type="primary",disabled=unresolved):
                st.session_state["remapped_project"]=apply_schema_mapping(project,mappings).model_dump(); st.rerun()
    if metadata_changes and any(metadata_changes.values()):
        with st.expander("REDCap metadata differences",expanded=True): st.json(metadata_changes)
elif step.startswith("2"):
    st.subheader("Understand each dataset")
    st.caption("Review field types and labels. Only five example rows are available behind the preview panel.")
    inspected_name=st.selectbox("Dataset",list(datasets_by_name),key="inspect-dataset")
    ds=datasets_by_name[inspected_name]
    st.write(f"Likely grain: **{ds.structure}** · Candidate key: **{' + '.join(ds.candidate_key) or 'none'}**")
    profile=profile_dataset(ds.data,ds.name,metadata)
    query=st.text_input("Filter variable name or label")
    types=st.multiselect("Data types",sorted(profile.inferred_type.unique()))
    if query: profile=profile[profile.original_name.str.contains(query,case=False,regex=False)|profile.variable_label.str.contains(query,case=False,regex=False)]
    if types: profile=profile[profile.inferred_type.isin(types)]
    st.dataframe(profile,hide_index=True,use_container_width=True)
    with st.expander("Small row preview (first 5 rows)"): st.dataframe(ds.data.head(5),hide_index=True)
    if st.checkbox("Run optional privacy scan"):
        flags=privacy_scan(ds.data); st.warning("Flags are suggestions only. No fields are automatically removed.")
        st.dataframe(flags,hide_index=True,use_container_width=True)
elif step.startswith("3"):
    st.subheader("Shared variables")
    st.dataframe(shared_variables(datasets),hide_index=True,use_container_width=True)
    st.subheader("Candidate identifiers")
    st.dataframe(score_identifiers(datasets),hide_index=True,use_container_width=True)
elif step.startswith("4"):
    st.subheader("Define how datasets connect")
    st.caption("Choose the fields that identify the same record or observation in both datasets. The app will check the join before it is used.")
    if len(datasets)<2:
        st.info("Add at least two datasets to define a relationship.")
        st.stop()
    left_name=st.selectbox("Left dataset",list(datasets_by_name),key="relationship-left")
    left=datasets_by_name[left_name]
    right_names=[name for name in datasets_by_name if name!=left_name]
    right_name=st.selectbox("Right dataset",right_names,key="relationship-right")
    right=datasets_by_name[right_name]
    common=[c for c in left.data if c in right.data]
    keys=st.multiselect("Confirmed linkage key(s)",common,default=[c for c in left.candidate_key if c in common],key=f"relationship-keys-{left_name}-{right_name}")
    if keys:
        diag=analyze_relationship(left.data,right.data,keys)
        a,b,c,d=st.columns(4); a.metric("Relationship",diag["relationship"]); b.metric("Matched keys",f"{diag['matched_key_pct']}%"); c.metric("Expected rows",diag["expected_rows"]); d.metric("Duplicate-key rows",diag["left_duplicate_keys"]+diag["right_duplicate_keys"])
        with st.expander("Detailed join diagnostics"): st.json(diag)
        if diag["unsafe"]: st.error("Many-to-many hazard: a direct join may multiply rows. Keep linked tables, aggregate one side, or add a secondary key. Export requires explicit confirmation.")
        st.session_state["relationship"]={"left":left.name,"right":right.name,"keys":keys,"diagnostics":diag}
elif step.startswith("5"):
    st.subheader("Variable selection")
    st.caption("Linkage fields are highlighted by warnings if removed. Use the search box inside each selector to find fields quickly.")
    for ds in datasets:
        required=ds.candidate_key
        saved=[c for c in (project.selected_variables.get(ds.name,[]) if project else []) if c in ds.data]
        selected=st.multiselect(ds.name,list(ds.data.columns),default=saved or list(ds.data.columns),key=f"select-{ds.name}")
        missing=[k for k in required if k not in selected]
        if missing: st.warning(f"Required candidate keys excluded: {', '.join(missing)}")
        st.session_state[f"selected-{ds.name}"]=selected
    st.caption("Clean Stata-name crosswalk")
    st.dataframe(pd.concat([name_crosswalk(d.data,d.name) for d in datasets]),hide_index=True,use_container_width=True)
elif step.startswith("6"):
    st.subheader("Prepare data")
    st.caption("Build a short, reproducible recipe. Every action is applied to an export copy—your imported files remain unchanged.")
    if "transformations" not in st.session_state:
        st.session_state["transformations"]=list(project.transformations) if project else []
    transform_name=st.selectbox("Dataset to prepare",list(datasets_by_name),key="transform-dataset")
    transform_ds=datasets_by_name[transform_name]
    operation_names={"trim":"Trim spaces","case":"Standardise letter case","rename":"Rename a field","change_type":"Change field type","date_part":"Extract year or month","binary_indicator":"Create yes/no indicator","row_count":"Add a row total","remove_duplicates":"Remove duplicate rows"}
    operation_type=st.selectbox("Action",list(operation_names),format_func=lambda x:operation_names[x])
    operation={"dataset":transform_ds.name,"type":operation_type}
    if operation_type not in {"remove_duplicates","row_count"}:
        operation["column"]=st.selectbox("Field",list(transform_ds.data.columns),key="operation-column")
    if operation_type=="case": operation["mode"]=st.selectbox("Case",["lower","upper","title"],format_func=str.title)
    elif operation_type=="rename": operation["new_name"]=st.text_input("New field name")
    elif operation_type=="change_type":
        operation["target"]=st.selectbox("New type",["string","integer","float","date","datetime"])
        if operation["target"] in {"date","datetime"}: operation["format"]=st.text_input("Exact date format",value="%Y-%m-%d",help="Examples: %Y-%m-%d or %d/%m/%Y. Ambiguous dates are never guessed.")
        elif operation["target"] in {"integer","float"}:
            decimal_label=st.selectbox("Decimal separator",["Full stop: 12.5","Comma: 12,5"],key="numeric-decimal")
            operation["decimal_separator"]="," if decimal_label.startswith("Comma") else "."
            thousands_options={"None":"","Comma: 1,000":",","Full stop: 1.000":".","Space: 1 000":" ","Apostrophe: 1'000":"'"}
            thousands_label=st.selectbox("Thousands separator",list(thousands_options),key="numeric-thousands")
            operation["thousands_separator"]=thousands_options[thousands_label]
            missing_raw=st.text_input("Treat these as missing",value="NA, N/A, NAN, NULL, NONE, MISSING, UNKNOWN, NOT KNOWN, NOT APPLICABLE, NOT DONE, REFUSED",help="Case-insensitive, comma-separated tokens. Blank cells are always treated as missing.",key="numeric-missing")
            operation["missing_values"]=[value.strip() for value in missing_raw.split(",")]+[""]
            policy_label=st.radio("Other invalid values",["Block and show the number of invalid values","Set them to missing and continue"],key="numeric-invalid-policy")
            operation["invalid_policy"]="set_missing" if policy_label.startswith("Set") else "block"
            if operation["invalid_policy"]=="set_missing": st.warning("Unrecognized values will become missing in the export. This decision will be recorded in the project recipe.")
            if operation["thousands_separator"]==operation["decimal_separator"]: st.error("Choose different decimal and thousands separators.")
    elif operation_type=="date_part":
        operation["part"]=st.selectbox("Part",["year","month"]); operation["new_name"]=st.text_input("New field name",value=f"{operation['column']}_{operation['part']}")
    elif operation_type=="binary_indicator":
        raw=st.text_input("Values that mean yes",help="Comma-separated exact values, for example: Active, Current")
        operation["values"]=[v.strip() for v in raw.split(",") if v.strip()]; operation["new_name"]=st.text_input("New field name",value=f"{operation['column']}_flag")
    elif operation_type=="row_count":
        operation["columns"]=st.multiselect("Fields to add",list(transform_ds.data.columns)); operation["new_name"]=st.text_input("New field name",value="row_total")
    elif operation_type=="remove_duplicates": operation["columns"]=st.multiselect("Fields defining a duplicate (leave blank for whole row)",list(transform_ds.data.columns)) or None
    invalid=(operation_type in {"rename","date_part","binary_indicator","row_count"} and not operation.get("new_name")) or (operation_type=="change_type" and operation.get("target") in {"integer","float"} and operation.get("decimal_separator")==operation.get("thousands_separator"))
    if st.button("Add action",type="primary",disabled=invalid):
        st.session_state["transformations"].append(operation); st.rerun()

    current_ops=[op for op in st.session_state["transformations"] if op.get("dataset")==transform_ds.name]
    if current_ops:
        st.markdown("#### Recipe")
        for index,op in enumerate(current_ops,1): st.write(f"{index}. **{operation_names.get(op['type'],op['type'])}** · `{op.get('column','dataset')}`")
        left_button,right_button=st.columns(2)
        if left_button.button("Undo last action"):
            absolute=max(i for i,op in enumerate(st.session_state["transformations"]) if op.get("dataset")==transform_ds.name); st.session_state["transformations"].pop(absolute); st.rerun()
        if right_button.button("Clear this recipe"):
            st.session_state["transformations"]=[op for op in st.session_state["transformations"] if op.get("dataset")!=transform_ds.name]; st.rerun()
        try:
            preview=apply_transformations(transform_ds.data,current_ops)
            st.success(f"Recipe is valid: {len(preview):,} rows × {len(preview.columns):,} fields")
            with st.expander("Preview prepared data"): st.dataframe(preview.head(5),hide_index=True,use_container_width=True)
        except Exception as exc: st.error(f"Recipe needs attention: {exc}")
    else: st.info("No preparation actions yet. Add one above only if the exported data need it.")

    st.markdown("#### Checkbox output")
    for ds in datasets:
        groups=checkbox_groups(list(ds.data.columns))
        if groups:
            st.markdown(f"**{ds.name} checkbox groups**")
            for group, columns in groups.items():
                mode=st.selectbox(group,["separate","combined_labels","combined_codes","long"],format_func=lambda x:{"separate":"Separate binary indicators","combined_labels":"Combined label string","combined_codes":"Combined code string","long":"Long-format table"}[x],key=f"checkbox-{ds.name}-{group}")
                st.session_state[f"checkbox-mode-{ds.name}-{group}"]=mode
                labels=[field_metadata(metadata,c)["checkbox_label"] or c for c in columns]
                st.caption(f"Options: {', '.join(labels)}")
elif step.startswith("7"):
    st.subheader("Check data quality")
    st.caption("Errors block export when integrity may be compromised. Warnings need review; information items are advisory.")
    findings=[]
    for ds in datasets:
        try: checked=apply_transformations(ds.data,[op for op in st.session_state.get("transformations",[]) if op.get("dataset")==ds.name])
        except Exception as exc:
            findings.append({"file":ds.name,"severity":"error","check":"transformation","variable":"","message":str(exc)}); checked=ds.data
        for f in validate_dataset(checked,ds.candidate_key): findings.append({"file":ds.name,**f})
    if metadata:
        for ds in datasets:
            for c in ds.data:
                meta=field_metadata(metadata,c)
                if meta["choices"] and not meta["checkbox_code"]:
                    allowed=set(meta["choices"]); observed=set(ds.data[c].dropna().astype(str))
                    invalid=observed-allowed
                    if invalid: findings.append({"file":ds.name,"severity":"warning","check":"invalid_category_codes","variable":c,"message":f"{len(invalid)} unrecognised category code(s)"})
    st.dataframe(pd.DataFrame(findings),hide_index=True,use_container_width=True) if findings else st.success("No findings for inferred keys and metadata.")
elif step.startswith("8"):
    st.subheader("Download results")
    st.info("Separate linked tables are the safest default when diagnoses, medications, or other repeating observations are present.")
    output_mode=st.radio("Layout",["Separate linked tables (recommended)","One combined table"],horizontal=True)
    fmt=st.radio("File format",["Stata files (ZIP)","Excel workbook","CSV files (ZIP)"],horizontal=True)
    selected={d.name:d.data[st.session_state.get(f"selected-{d.name}",list(d.data.columns))].copy() for d in datasets}
    transformation_errors=[]
    for d in datasets:
        try: selected[d.name]=apply_transformations(selected[d.name],[op for op in st.session_state.get("transformations",[]) if op.get("dataset")==d.name])
        except Exception as exc: transformation_errors.append(f"{d.name}: {exc}")
    if transformation_errors:
        st.error("Export is blocked because a preparation action failed: " + " · ".join(transformation_errors)); st.stop()
    checkbox_modes={}
    for d in datasets:
        for group in checkbox_groups(list(selected[d.name].columns)):
            mode=st.session_state.get(f"checkbox-mode-{d.name}-{group}",(project.checkbox_modes.get(f"{d.name}:{group}") if project else "separate") or "separate")
            checkbox_modes[f"{d.name}:{group}"]=mode
            if mode!="separate": selected[d.name]=transform_checkbox_group(selected[d.name],group,mode,metadata)
    merge_summary=None
    if output_mode.startswith("One combined"):
        rel=st.session_state.get("relationship")
        if not rel or rel["left"] not in selected or rel["right"] not in selected:
            st.error("Define and confirm a relationship in Step 4 before creating a combined table."); st.stop()
        keys=rel["keys"]; missing_keys=[f"{name}: {key}" for name in [rel["left"],rel["right"]] for key in keys if key not in selected[name]]
        if missing_keys: st.error("Combined export is blocked because linkage fields are unavailable after selection or preparation: "+", ".join(missing_keys)); st.stop()
        diagnostics=analyze_relationship(selected[rel["left"]],selected[rel["right"]],keys)
        confirm=False
        if diagnostics["unsafe"]:
            st.error("This is a many-to-many join and may multiply rows.")
            confirm=st.checkbox("I understand the row-multiplication risk and want to create this combined table")
            if not confirm: st.stop()
        combined=safe_merge(selected[rel["left"]],selected[rel["right"]],keys,confirm_many_to_many=confirm)
        merge_summary={**diagnostics,"actual_rows":len(combined),"keys":keys,"left":rel["left"],"right":rel["right"]}
        selected={"combined":combined}
    manifest=build_manifest(datasets, selected_variables={k:list(v.columns) for k,v in selected.items()}, transformations=st.session_state.get("transformations",[]), checkbox_modes=checkbox_modes, merge_diagnostics=merge_summary, warnings=[])
    config=ProjectConfig(sources=[{"filename":d.name,"sha256":d.file_hash} for d in datasets],selected_variables={d.name:st.session_state.get(f"selected-{d.name}",list(d.data.columns)) for d in datasets},linkage_keys={d.name:d.candidate_key for d in datasets},relationships=[st.session_state["relationship"]] if st.session_state.get("relationship") else [],schemas={d.name:dataset_schema(d.data) for d in datasets},metadata_snapshot=metadata,checkbox_modes=checkbox_modes,structure_overrides={d.name:d.structure for d in datasets},transformations=st.session_state.get("transformations",[]),output_settings={"mode":"flat" if output_mode.startswith("One") else "relational","format":fmt})
    totals=pd.DataFrame([{"dataset":name,"rows":len(df),"fields":len(df.columns)} for name,df in selected.items()])
    st.dataframe(totals,hide_index=True,use_container_width=True)
    st.download_button("Save reproducible project",project_to_bytes(config),"redcap_explorer_project.json","application/json")
    if st.session_state.get("schema_blocking"):
        st.error("Export is disabled because required variables from the saved project are missing.")
        st.stop()
    if fmt.startswith("Stata"):
        out=io.BytesIO()
        try:
            with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
                all_cross=[]
                for name,df in selected.items():
                    labels={c:field_metadata(metadata,c)["label"] for c in df.columns}
                    values=value_labels_for_columns(metadata,list(df.columns))
                    export_keys=merge_summary["keys"] if name=="combined" and merge_summary else next(d.candidate_key for d in datasets if d.name==name)
                    dta,do,cross=export_stata_bytes(df,labels,values,[name],export_keys)
                    stem=Path(name).stem; z.writestr(f"{stem}.dta",dta); z.writestr(f"{stem}.do",do); all_cross.append(cross.assign(source_file=name))
                z.writestr("variable_crosswalk.csv",pd.concat(all_cross).to_csv(index=False))
                z.writestr("processing_manifest.json",json.dumps(manifest,indent=2))
        except Exception as exc:
            st.error(f"Stata export could not be created: {exc}")
            st.info("No output was saved. Review the named field or choose Excel/CSV while correcting its type.")
            st.stop()
        st.download_button("Download local Stata export",out.getvalue(),"redcap_stata_export.zip","application/zip")
    elif fmt.startswith("Excel"):
        out=io.BytesIO(); used=set()
        with pd.ExcelWriter(out,engine="openpyxl") as writer:
            for name,df in selected.items():
                sheet=Path(name).stem[:31]; df.to_excel(writer,sheet_name=sheet,index=False)
            pd.concat([name_crosswalk(df,name) for name,df in selected.items()]).to_excel(writer,sheet_name="Variable crosswalk",index=False)
            pd.DataFrame(manifest["inputs"]).to_excel(writer,sheet_name="Processing report",index=False)
        st.download_button("Download local Excel export",out.getvalue(),"redcap_export.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
            for name,df in selected.items(): z.writestr(Path(name).with_suffix(".csv").name,df.to_csv(index=False))
            z.writestr("processing_manifest.json",json.dumps(manifest,indent=2))
        st.download_button("Download local relational export",out.getvalue(),"redcap_relational_export.zip","application/zip")
    st.download_button("Download processing manifest",json.dumps(manifest,indent=2),"processing_manifest.json","application/json")
