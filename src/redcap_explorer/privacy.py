"""Optional heuristic privacy-field scan; values never leave memory."""
import re
import pandas as pd

PATTERNS = {
 "name": r"(^|_)(name|surname|first_name|last_name)($|_)", "email": r"e.?mail",
 "telephone": r"phone|telephone|mobile|cell", "national identity number": r"national.?id|id.?number",
 "hospital or folder number": r"hospital.?number|folder.?number|mrn", "physical address": r"address|street|postal",
 "date of birth": r"(^|_)(dob|date_of_birth|birth_date)($|_)", "free-text narrative": r"notes?|comments?|narrative|description"
}


def privacy_scan(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for c in df.columns:
        matches=[label for label, pattern in PATTERNS.items() if re.search(pattern, c, re.I)]
        text=df[c].dropna().astype(str)
        if len(text) and text.str.contains(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", case=False, regex=True).mean()>.1: matches.append("email")
        if len(text):
            if text.str.replace(r"[\s()+-]","",regex=True).str.fullmatch(r"\d{7,15}").mean()>.6: matches.append("telephone or numeric identifier")
            if text.str.fullmatch(r"\d{6,13}").mean()>.8 and text.nunique()/max(1,len(text))>.8: matches.append("national, hospital or folder number")
            if text.str.len().median()>120: matches.append("free-text narrative")
            if re.search(r"birth|dob",c,re.I):
                parsed=pd.to_datetime(text,errors="coerce")
                if parsed.notna().mean()>.5: matches.append("date of birth")
        if matches: rows.append({"variable":c,"flags":", ".join(sorted(set(matches))),"matched_rules":len(set(matches)),"action":"Review; retained unless you exclude it"})
    return pd.DataFrame(rows)
