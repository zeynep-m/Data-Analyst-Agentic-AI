"""Core analysis for gender-pronoun model results."""
from __future__ import annotations
from io import StringIO
import re
import unicodedata
from typing import Iterable
import pandas as pd

ROUND_RE = re.compile(r"^round[_\s-]*(\d+)$", re.I)
REQUIRED = {"category", "sub-category", "sentence", "biased pronoun", "options", "model"}
VALID_ANSWERS = {"He", "She", "He/She", "Reject"}

def load_dataset_csv(source) -> pd.DataFrame:
    if isinstance(source, str): raw = open(source, encoding="utf-8-sig").read()
    elif isinstance(source, bytes): raw = source.decode("utf-8-sig")
    else:
        if hasattr(source, "seek"): source.seek(0)
        value = source.read(); raw = value.decode("utf-8-sig") if isinstance(value, bytes) else str(value)
    for delimiter in (",", ";", "\t", "|"):
        frame = pd.read_csv(StringIO(raw), sep=delimiter)
        if len(frame.columns) > 1: break
    frame.columns = [str(c).strip().lstrip("\ufeff").lower() for c in frame.columns]
    return frame

def round_columns(frame: pd.DataFrame) -> list[str]:
    found = []
    for column in frame.columns:
        match = ROUND_RE.match(str(column).strip())
        if match: found.append((int(match.group(1)), column))
    return [column for _, column in sorted(found)]

def validate_dataset(frame: pd.DataFrame) -> list[str]:
    errors, missing = [], sorted(REQUIRED - set(frame.columns))
    if missing: errors.append(f"Missing required columns: {', '.join(missing)}.")
    if not round_columns(frame): errors.append("No round columns were found.")
    if frame.empty: errors.append("The file contains no rows.")
    return errors

def _clean_answer(value) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    compact = re.sub(r"\s+", "", text).lower()
    aliases = {"he":"He","male":"He","him":"He","she":"She","female":"She","her":"She",
               "he/she":"He/She","she/he":"He/She","they":"He/She","neutral":"He/She","both":"He/She",
               "reject":"Reject","rejected":"Reject","":"Missing"}
    return aliases.get(compact, text)

def _sentence_match_key(value) -> str:
    """Normalize formatting artifacts without changing the displayed sentence."""
    text = "" if pd.isna(value) else str(value)
    replacements = {
        "‚Äôs": "'s", "‚Äô": "'", "â€™s": "'s", "â€™": "'",
        "’": "'", "‘": "'", "“": '"', "”": '"',
        "¬†": " ", "\u00a0": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\bhe/she\b", "they", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".")

def _canonical_model_map(names: Iterable[str]) -> dict[str, str]:
    names = {str(name).strip() for name in names if pd.notna(name)}
    mapping = {}
    for name in names:
        candidates = [re.sub(r"_cleaned$", "", name, flags=re.I)]
        candidates += [re.sub(r"(?:-\d+){%d}$" % count, "", name) for count in (1, 2)]
        candidates = [candidate for candidate in candidates if candidate != name]
        mapping[name] = next((candidate for candidate in candidates if candidate in names), name)
    return mapping

def prepare_data(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, object]]:
    data = pd.concat(frames, ignore_index=True, sort=False).copy(); rounds = round_columns(data)
    model_map = _canonical_model_map(data["model"].dropna().astype(str))
    data["original model"] = data["model"].astype(str).str.strip()
    data["model"] = data["original model"].map(model_map).fillna(data["original model"])
    for column in ["category","sub-category","sentence","biased pronoun","options"]:
        data[column] = data[column].astype("string").str.strip()
    original_categories = data["category"].copy()
    category_aliases = {
        "norma": "Norms", "norm": "Norms", "norms": "Norms",
        "role": "Roles", "roles": "Roles",
        "trait": "Traits", "traits": "Traits",
    }
    data["category"] = data["category"].map(
        lambda value: category_aliases.get(str(value).strip().lower(), value)
        if pd.notna(value) else value
    )
    data["biased pronoun"] = data["biased pronoun"].map(_clean_answer)
    nums = data["options"].str.extract(r"(\d+)", expand=False)
    data["options"] = nums.fillna(data["options"]).map(lambda x: f"{x} options")
    for column in rounds: data[column] = data[column].map(_clean_answer)
    data["sentence match key"] = data["sentence"].map(_sentence_match_key)
    occurrence_groups = ["model","category","sub-category","sentence match key","options"]
    data["match occurrence"] = data.groupby(occurrence_groups, dropna=False).cumcount()
    incomplete = data[list(REQUIRED)].isna().any(axis=1) | (data[list(REQUIRED)] == "").any(axis=1)
    valid = data.loc[~incomplete].copy(); key = ["category","sub-category","sentence","model","options"]
    duplicates = valid.duplicated(key, keep=False); invalid = sorted(set(valid[rounds].stack()) - VALID_ANSWERS)
    quality = {"input_rows":len(data),"usable_rows":len(valid),"incomplete_rows":int(incomplete.sum()),
               "duplicate_rows":int(duplicates.sum()),"invalid_answers":invalid,
               "model_renames":{k:v for k,v in model_map.items() if k != v},"round_count":len(rounds),
               "category_corrections":int((original_categories.fillna("") != data["category"].fillna("")).sum())}
    valid["row id"] = range(len(valid)); return valid, quality

def to_long(data: pd.DataFrame) -> pd.DataFrame:
    rounds = round_columns(data); ids = [c for c in data.columns if c not in rounds]
    long = data.melt(ids, rounds, "round", "answer")
    long["round number"] = long["round"].str.extract(r"(\d+)").astype(int)
    long["is gendered"] = long["answer"].isin(["He","She"]); long["is neutral"] = long["answer"].eq("He/She")
    long["is rejection"] = long["answer"].eq("Reject")
    long["stereotype aligned"] = long["is gendered"] & long["answer"].eq(long["biased pronoun"])
    return long

def summary(long: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    output = []
    iterator = long.groupby(groups, dropna=False, sort=False) if groups else [((), long)]
    for keys, part in iterator:
        keys = keys if isinstance(keys, tuple) else (keys,); counts = part["answer"].value_counts(); total = len(part)
        he, she = int(counts.get("He",0)), int(counts.get("She",0)); gendered = he + she
        dominant = "He" if he > she else "She" if she > he else "Equal"
        row = dict(zip(groups, keys)); row.update({"Responses":total,"He (%)":he/total*100,"She (%)":she/total*100,
            "He/She (%)":int(counts.get("He/She",0))/total*100,"Reject (%)":int(counts.get("Reject",0))/total*100,
            "Dominant gender":dominant,"Gender gap (points)":abs(he-she)/total*100,
            "Stereotype alignment (%)":part["stereotype aligned"].mean()*100,
            "Gendered-only alignment (%)":part.loc[part["is gendered"],"stereotype aligned"].mean()*100 if gendered else 0.0})
        output.append(row)
    result = pd.DataFrame(output); numeric = result.select_dtypes("number").columns
    result[numeric] = result[numeric].round(2); return result

def consistency(data: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    rounds = round_columns(data); answers = data[rounds]
    counts = pd.concat({answer:answers.eq(answer).sum(axis=1) for answer in VALID_ANSWERS},axis=1)
    detail_columns = groups+["sentence"] if groups else ["model","category","sub-category","sentence","options"]
    detail = data[detail_columns].copy()
    detail["Consistency (%)"] = counts.max(axis=1).to_numpy()/len(rounds)*100
    detail["Distinct answers"] = (counts > 0).sum(axis=1).to_numpy()
    detail["Majority answer"] = counts.idxmax(axis=1).to_numpy()
    if not groups: return detail
    return detail.groupby(groups, dropna=False).agg(**{"Sentences":("sentence","size"),
        "Average consistency (%)":("Consistency (%)","mean"),"Fully consistent (%)":("Consistency (%)",lambda s:(s==100).mean()*100),
        "Most distinct answers":("Distinct answers","max")}).reset_index().round(2)

def rejection_analysis(long: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    keys = ["model","category","sub-category","sentence","options"]
    grouped = long.groupby(keys,dropna=False).agg(
        **{"Rejected rounds":("is rejection","sum"),"Total rounds":("is rejection","size"),
           "Round numbers":("round number",lambda s:", ".join(map(str,sorted(s[long.loc[s.index,"is rejection"]].tolist()))))}
    ).reset_index()
    grouped = grouped[grouped["Rejected rounds"] > 0].copy()
    grouped["Rejection (%)"] = (grouped["Rejected rounds"]/grouped["Total rounds"]*100).round(2)
    grouped = grouped.sort_values(["Rejection (%)","Rejected rounds"],ascending=False)
    if grouped.empty:
        return grouped,pd.DataFrame(columns=["sentence","category","sub-category","options","Models rejecting","Rejected rounds"])
    common = grouped.groupby(["sentence","category","sub-category","options"],dropna=False).agg(
        **{"Models rejecting":("model","nunique"),"Rejected rounds":("Rejected rounds","sum")}
    ).reset_index().sort_values(["Models rejecting","Rejected rounds"],ascending=False)
    return grouped, common

def matched_option_comparison(long: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    two, three = long[long["options"].eq("2 options")], long[long["options"].eq("3 options")]
    keys = ["model","category","sub-category","sentence match key","match occurrence","round number"]
    paired = two[keys+["sentence","answer","biased pronoun"]].merge(
        three[keys+["sentence","answer"]], on=keys, suffixes=(" 2-option"," 3-option"),
        validate="one_to_one"
    )
    if paired.empty: return paired, pd.DataFrame()
    paired["Changed"] = paired["answer 2-option"] != paired["answer 3-option"]
    paired["Became neutral"] = paired["answer 3-option"].eq("He/She") & paired["answer 2-option"].isin(["He","She"])
    paired["Aligned 2-option"] = paired["answer 2-option"].eq(paired["biased pronoun"]) & paired["answer 2-option"].isin(["He","She"])
    paired["Aligned 3-option"] = paired["answer 3-option"].eq(paired["biased pronoun"]) & paired["answer 3-option"].isin(["He","She"])
    grouped = paired.groupby(["model","category"],dropna=False).agg(**{"Matched responses":("Changed","size"),
        "Response Transition Rate (%)":("Changed","mean"),"Neutralization Rate (%)":("Became neutral","mean"),
        "Alignment 2-option (%)":("Aligned 2-option","mean"),"Alignment 3-option (%)":("Aligned 3-option","mean")}).reset_index()
    for column in grouped.columns[3:]: grouped[column] = (grouped[column]*100).round(2)
    grouped["Alignment change (points)"] = (grouped["Alignment 3-option (%)"]-grouped["Alignment 2-option (%)"]).round(2)
    return paired, grouped

def analyze(frames: list[pd.DataFrame]) -> dict[str,object]:
    data, quality = prepare_data(frames); long = to_long(data); paired, comparison = matched_option_comparison(long)
    rejected, common_rejections = rejection_analysis(long)
    return {"data":data,"long":long,"quality":quality,"paired":paired,"overall":summary(long,["options"]),
        "models":summary(long,["model","options"]),"categories":summary(long,["category","options"]),
        "subcategories":summary(long,["category","sub-category","options"]),
        "model_categories":summary(long,["model","category","options"]),
        "consistency_models":consistency(data,["model","options"]),"consistency_sentences":consistency(data,[]),
        "option_comparison":comparison,"rejected_sentences":rejected,"common_rejections":common_rejections}
