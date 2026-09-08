from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


SOURCE = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Consolidated_Model_Evaluations_with_Custom_Error_Bars_Updated.xlsx"
)
THESIS = Path("/Users/justintiensmith/Documents/MSc_Thesis_Bar_Charts.xlsx")
OUT = Path(__file__).resolve().parent

MODEL_SHEETS = {
    "VLA-0": "VLA-0",
    "GR00T Full FT": "GR00T Full",
    "GR00T Frozen LLM": "GR00T Vision",
    "Pi0.5": "Pi0.5",
    "MolmoAct2": "MolmoAct2",
}
COMPLETE_MODELS = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"]
TASK_ORDER = [
    "Counting",
    "Ordinal Reference Ordering",
    "Relational Placement",
    "State Recognition",
    "Size Recognition",
    "Referential Disambiguation",
]

USER_CORRECTIONS = {
    ("MolmoAct2", "Size Recognition", 17): "Success",
    ("Pi0.5", "Referential Disambiguation", 47): "Success",
}


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if trials <= 0:
        return math.nan, math.nan
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denominator
    return max(0, center - half), min(1, center + half)


def load_evaluations() -> pd.DataFrame:
    rows = []
    for model, sheet in MODEL_SHEETS.items():
        frame = pd.read_excel(SOURCE, sheet_name=sheet)
        frame = frame[frame["Status"].isin(["Success", "Failure"])].copy()
        frame["Model"] = model
        for idx, row in frame.iterrows():
            correction = USER_CORRECTIONS.get((model, str(row["Task"]), int(row["Episode"])))
            if correction:
                frame.at[idx, "Status"] = correction
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def aggregate(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    result = (
        frame.assign(Success=frame["Status"].eq("Success").astype(int))
        .groupby(group_cols, dropna=False)
        .agg(Successes=("Success", "sum"), Scored=("Success", "size"))
        .reset_index()
    )
    result["Rate"] = result["Successes"] / result["Scored"]
    bounds = result.apply(lambda row: wilson(int(row["Successes"]), int(row["Scored"])), axis=1)
    result["CI Lower"] = [value[0] for value in bounds]
    result["CI Upper"] = [value[1] for value in bounds]
    result["Lower Error"] = result["Rate"] - result["CI Lower"]
    result["Upper Error"] = result["CI Upper"] - result["Rate"]
    return result


def build_expected(data: pd.DataFrame) -> dict[str, list[dict]]:
    expected: dict[str, list[dict]] = {}

    familiar = data[data["Condition"].eq("In-distribution concept baseline")]
    expected["Familiar Spatial Task Chart"] = aggregate(familiar, ["Task", "Model"]).to_dict("records")

    novel = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Condition"].eq("Concept/compositional transfer")
    ]
    expected["Novel Spatial Task Chart"] = aggregate(novel, ["Task", "Model"]).to_dict("records")

    matched = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Condition"].eq("Matched manipulation control")
    ]
    expected["Matched Manipulation Task Chart"] = aggregate(matched, ["Task", "Model"]).to_dict("records")

    no_movement_conditions = [
        "Goal already satisfied / no movement",
        "Invalid ordinal / no-movement diagnostic",
        "No valid target / no movement",
        "No valid candidate category / no movement",
    ]
    no_move = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Condition"].isin(no_movement_conditions)
        & data["Task"].ne("Relational Placement")
    ]
    no_move_rows = aggregate(no_move, ["Task", "Condition", "Model"]).to_dict("records")
    no_move_rows += aggregate(no_move, ["Model"]).assign(Task="Aggregate across four tasks", Condition="Aggregate").to_dict("records")
    expected["No Movement"] = no_move_rows

    relational = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Task"].eq("Relational Placement")
        & data["Condition"].isin([
            "Goal already satisfied / no movement",
            "Violated-relation correction control",
        ])
    ]
    expected["Relational Movement No Movement"] = aggregate(relational, ["Condition", "Model"]).to_dict("records")

    standard = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Task"].ne("State Recognition")
        & data["Condition"].eq("In-distribution concept baseline")
    ]
    cross = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Task"].ne("State Recognition")
        & data["Condition"].astype(str).str.startswith("Cross-task")
    ]
    cross_rows = aggregate(standard, ["Model"]).assign(Category="Familiar spatial grounding, standard objects")
    cross_rows = pd.concat([
        cross_rows,
        aggregate(cross, ["Model"]).assign(Category="Familiar spatial grounding, cross-task objects"),
    ], ignore_index=True)
    expected["Cross Task Object Chart v2"] = cross_rows.to_dict("records")

    language = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Condition"].eq("Language robustness")
    ].copy()
    subtype = language["Comparison / Subtype"].astype(str)
    language["Group"] = "Novel Spatial Grounding"
    language.loc[
        subtype.str.contains("Matched-control|Direct-category", regex=True) | subtype.eq("Direct"),
        "Group",
    ] = "Matched Manipulation"
    language["Paraphrased Success"] = language["Status"].eq("Success").astype(int)

    matching_fields = [
        "Object Count",
        "Valid Candidate Count",
        "Bowl Start",
        "Queried State",
        "Queried Category",
        "Contrast Pair",
        "Initial Bowl Count",
        "Goal Count",
        "Action Direction",
        "Target Position",
        "Query Concept",
        "Relation",
        "Target Object",
        "Reference Object",
        "Juggling Ball Role",
        "Candidate Category",
        "Target Side",
        "Separation (cm)",
        "Tested Cell / Role",
    ]

    def original_status(row: pd.Series) -> str:
        if row["Group"] == "Novel Spatial Grounding":
            reference_episode = int(row["Reference Episode"])
            candidates = data[
                data["Model"].eq(row["Model"])
                & data["Task"].eq(row["Task"])
                & data["Condition"].eq("Concept/compositional transfer")
                & (
                    data["Episode"].eq(reference_episode)
                    | data["Reference Episode"].eq(reference_episode)
                )
            ]
        else:
            reference_episode = int(row["Reference Episode"])
            candidates = data[
                data["Model"].eq(row["Model"])
                & data["Task"].eq(row["Task"])
                & data["Condition"].eq("Matched manipulation control")
                & data["Scene Family"].eq(row["Scene Family"])
                & (
                    data["Episode"].eq(reference_episode)
                    | data["Reference Episode"].eq(reference_episode)
                )
            ]
        if len(candidates) > 1:
            for field in matching_fields:
                value = row[field]
                if pd.isna(value):
                    continue
                narrowed = candidates[candidates[field].notna() & candidates[field].eq(value)]
                if not narrowed.empty:
                    candidates = narrowed
                if len(candidates) == 1:
                    break
        if len(candidates) != 1:
            raise ValueError(
                f"Expected one original row for {row['Model']}, {row['Task']}, "
                f"episode {row['Episode']}; found {len(candidates)}"
            )
        return str(candidates.iloc[0]["Status"])

    language["Original Status"] = language.apply(original_status, axis=1)
    language["Original Success"] = language["Original Status"].eq("Success").astype(int)
    paraphrase_rows = []
    for (group, model), group_frame in language.groupby(["Group", "Model"]):
        n = len(group_frame)
        for phrasing, column in [("Original", "Original Success"), ("Paraphrased", "Paraphrased Success")]:
            successes = int(group_frame[column].sum())
            low, high = wilson(successes, n)
            paraphrase_rows.append({
                "Group": group,
                "Model": model,
                "Phrasing": phrasing,
                "Successes": successes,
                "Scored": n,
                "Rate": successes / n,
                "CI Lower": low,
                "CI Upper": high,
                "Lower Error": successes / n - low,
                "Upper Error": high - successes / n,
            })
    expected["Paraphrasing Comparison v3"] = paraphrase_rows

    overall_rows = []
    for label, subset in [
        ("Novel Spatial Concepts", novel),
        ("Familiar Spatial Concepts", familiar[familiar["Model"].isin(COMPLETE_MODELS)]),
        ("Matched Manipulation Control", matched),
    ]:
        grouped = aggregate(subset, ["Model"])
        grouped["Evaluation track"] = label
        overall_rows.extend(grouped.to_dict("records"))
    expected["Sheet2"] = overall_rows
    expected["Emergent Skills Data"] = overall_rows
    return expected


def make_report(expected: dict[str, list[dict]]) -> None:
    serializable = json.loads(json.dumps(expected, default=str))
    (OUT / "expected_chart_data.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    for sheet, rows in expected.items():
        print(f"\n### {sheet}")
        for row in rows:
            identifying = {key: row[key] for key in ["Task", "Condition", "Category", "Evaluation track", "Group", "Model", "Phrasing"] if key in row}
            print({**identifying, "Successes": row["Successes"], "Scored": row["Scored"], "Rate": round(row["Rate"], 6), "CI": [round(row["CI Lower"], 6), round(row["CI Upper"], 6)]})


def main() -> None:
    data = load_evaluations()
    expected = build_expected(data)
    make_report(expected)


if __name__ == "__main__":
    main()
