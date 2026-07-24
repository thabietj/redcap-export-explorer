"""REDCap data-dictionary normalization and choice metadata."""
from __future__ import annotations
import re
from typing import Any, Dict


def metadata_value(row: Dict[str, Any], *names: str) -> str:
    normalized = {str(k).strip().lower(): str(v) for k, v in row.items()}
    return next((normalized[n.lower()] for n in names if normalized.get(n.lower())), "")


def parse_choices(raw: str) -> Dict[str, str]:
    """Parse REDCap's ``code, label | code, label`` representation."""
    choices: Dict[str, str] = {}
    for item in str(raw or "").split("|"):
        item = item.strip()
        if not item:
            continue
        code, separator, label = item.partition(",")
        if separator:
            choices[code.strip()] = label.strip()
    return choices


def field_metadata(dictionary: Dict[str, Dict[str, Any]], variable: str) -> Dict[str, Any]:
    """Resolve ordinary fields and expanded checkbox fields to normalized metadata."""
    base = re.sub(r"___[^_]+$", "", variable)
    row = dictionary.get(variable) or dictionary.get(base) or {}
    choices = parse_choices(metadata_value(row, "Choices, Calculations, OR Slider Labels", "Choices Calculations OR Slider Labels", "select_choices_or_calculations"))
    code_match = re.search(r"___([^_]+)$", variable)
    return {
        "field_name": base,
        "form_name": metadata_value(row, "Form Name", "form_name"),
        "field_type": metadata_value(row, "Field Type", "field_type"),
        "label": metadata_value(row, "Field Label", "field_label"),
        "choices": choices,
        "validation": metadata_value(row, "Text Validation Type OR Show Slider Number", "text_validation_type_or_show_slider_number"),
        "minimum": metadata_value(row, "Text Validation Min", "text_validation_min"),
        "maximum": metadata_value(row, "Text Validation Max", "text_validation_max"),
        "identifier": metadata_value(row, "Identifier?", "identifier") .lower() in {"y", "yes", "1", "true"},
        "required": metadata_value(row, "Required Field?", "required_field") .lower() in {"y", "yes", "1", "true"},
        "branching_logic": metadata_value(row, "Branching Logic", "branching_logic"),
        "matrix_group": metadata_value(row, "Matrix Group Name", "matrix_group_name"),
        "checkbox_code": code_match.group(1) if code_match else "",
        "checkbox_label": choices.get(code_match.group(1), "") if code_match else "",
    }


def value_labels_for_columns(dictionary: Dict[str, Dict[str, Any]], columns: list[str]) -> Dict[str, Dict[Any, str]]:
    result: Dict[str, Dict[Any, str]] = {}
    for column in columns:
        meta = field_metadata(dictionary, column)
        if meta["choices"] and not meta["checkbox_code"]:
            converted: Dict[Any, str] = {}
            for code, label in meta["choices"].items():
                try:
                    key: Any = int(code)
                except ValueError:
                    try: key = float(code)
                    except ValueError: key = code
                converted[key] = label
            result[column] = converted
        elif meta["checkbox_code"]:
            result[column] = {0: "Unchecked", 1: meta["checkbox_label"] or "Checked"}
    return result
