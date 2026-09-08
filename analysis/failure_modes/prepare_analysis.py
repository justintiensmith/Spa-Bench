from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
CLASSIFIED = ROOT / "failure_annotations_classified.csv"
PAYLOAD = ROOT / "analysis_payload.json"

COMPLETE_MODELS = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"]
TASK_ORDER = [
    "Physical State",
    "Relative Size",
    "Referential Description",
    "Ordinal Position",
    "Relational Placement",
    "Counting",
]
MODE_ORDER = [
    "Wrong target",
    "No action",
    "Correct target, incorrect spatial outcome",
    "Grasp failure",
    "Premature release or dropped object",
    "Timeout or incomplete execution",
    "Other execution failure",
    "Unannotated or unclear",
]

MODE_RENAMES = {
    "Incorrect spatial outcome": "Correct target, incorrect spatial outcome",
}


def matrix_payload() -> list[dict]:
    matrices: list[dict] = []

    matrices.append(
        {
            "task": "Physical State",
            "context": "",
            "rows": ["Open", "Closed", "Upright", "Upside-down"],
            "columns": ["White cup", "Striped cup", "Brown cup", "Spice container"],
            "values": [
                ["Observed", "Withheld", "Observed", "Observed"],
                ["Observed", "Observed", "Withheld", "Observed"],
                ["Observed", "Observed", "Observed", "Withheld"],
                ["Withheld", "Observed", "Observed", "Observed"],
            ],
        }
    )
    matrices.append(
        {
            "task": "Relative Size",
            "context": "",
            "rows": ["Largest", "Smallest"],
            "columns": ["Green block", "Crushed Pepsi can", "Red pencil sharpener", "Juggling ball"],
            "values": [
                ["Withheld", "Observed", "N/A", "Observed"],
                ["Observed", "N/A", "Observed", "Withheld"],
            ],
        }
    )
    matrices.append(
        {
            "task": "Referential Description",
            "context": "",
            "rows": ["Closest", "Furthest", "Between"],
            "columns": ["Airplane toys", "Crushed soda cans", "Pencil sharpeners", "Pens"],
            "values": [
                ["Observed", "Withheld", "Observed", "Observed"],
                ["Withheld", "Observed", "Observed", "Observed"],
                ["Observed", "Observed", "Withheld", "Observed"],
            ],
        }
    )

    ordinal_cols = ["Airplane toy\nwith propellers", "Blue tape ball", "Green highlighter", "Yellow pen"]
    matrices.extend(
        [
            {
                "task": "Ordinal Position",
                "context": "2-object sequences",
                "rows": ["L1", "L2"],
                "columns": ordinal_cols,
                "values": [
                    ["Withheld", "Observed", "Withheld", "Observed"],
                    ["Observed", "Withheld", "Observed", "Withheld"],
                ],
            },
            {
                "task": "Ordinal Position",
                "context": "3-object sequences",
                "rows": ["L1", "L2", "L3"],
                "columns": ordinal_cols,
                "values": [
                    ["Observed", "Withheld", "Observed", "Withheld"],
                    ["Absent", "Absent", "Absent", "Absent"],
                    ["Withheld", "Observed", "Withheld", "Observed"],
                ],
            },
            {
                "task": "Ordinal Position",
                "context": "4-object sequences",
                "rows": ["L1", "L2", "L3", "L4"],
                "columns": ordinal_cols,
                "values": [
                    ["Withheld", "Observed", "Observed", "Observed"],
                    ["Observed", "Withheld", "Observed", "Observed"],
                    ["Observed", "Observed", "Withheld", "Observed"],
                    ["Observed", "Observed", "Observed", "Withheld"],
                ],
            },
        ]
    )

    matrices.append(
        {
            "task": "Relational Placement",
            "context": "",
            "rows": ["Front", "Behind", "Left", "Right"],
            "columns": [
                "Green pen +\nred block",
                "Green pen +\npink marker",
                "Green pen +\nblue block",
                "Red block +\npink marker",
                "Red block +\nblue block",
                "Pink marker +\nblue block",
            ],
            "values": [
                ["Withheld", "Observed", "Observed", "Observed", "Observed", "Observed"],
                ["Withheld", "Observed", "Observed", "Observed", "Observed", "Observed"],
                ["Withheld", "Observed", "Observed", "Observed", "Observed", "Observed"],
                ["Withheld", "Observed", "Observed", "Observed", "Observed", "Observed"],
            ],
        }
    )
    matrices.append(
        {
            "task": "Counting",
            "context": "",
            "rows": ["0", "1", "2", "3"],
            "columns": ["Addition", "Removal"],
            "values": [
                ["N/A", "Observed"],
                ["Observed", "Withheld"],
                ["Observed", "Observed"],
                ["Withheld", "Observed"],
            ],
        }
    )
    return matrices


def main() -> None:
    all_failures = pd.read_csv(CLASSIFIED)
    all_failures["Canonical Task"] = all_failures["Canonical Task"].replace(
        {"State Recognition": "Physical State", "Size Recognition": "Relative Size"}
    )
    all_failures["Primary Failure Mode"] = all_failures["Primary Failure Mode"].replace(MODE_RENAMES)

    primary = all_failures[
        all_failures["Model"].isin(COMPLETE_MODELS)
        & all_failures["Condition"].eq("Concept/compositional transfer")
    ].copy()
    primary["Model"] = pd.Categorical(primary["Model"], COMPLETE_MODELS, ordered=True)
    primary["Canonical Task"] = pd.Categorical(primary["Canonical Task"], TASK_ORDER, ordered=True)
    primary["Primary Failure Mode"] = pd.Categorical(primary["Primary Failure Mode"], MODE_ORDER, ordered=True)
    primary = primary.sort_values(["Model", "Canonical Task", "Episode"])

    model_counts = (
        primary.groupby(["Model", "Primary Failure Mode"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(index=COMPLETE_MODELS, columns=MODE_ORDER, fill_value=0)
    )
    task_counts = (
        primary.groupby(["Canonical Task", "Primary Failure Mode"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(index=TASK_ORDER, columns=MODE_ORDER, fill_value=0)
    )
    overall_counts = primary["Primary Failure Mode"].value_counts().reindex(MODE_ORDER, fill_value=0)

    matrices = matrix_payload()
    long_cells: list[dict] = []
    for matrix in matrices:
        for row_name, row_values in zip(matrix["rows"], matrix["values"]):
            for col_name, status in zip(matrix["columns"], row_values):
                long_cells.append(
                    {
                        "Task": matrix["task"],
                        "Context": matrix["context"],
                        "Concept": row_name,
                        "Argument": col_name.replace("\n", " "),
                        "Status": status,
                    }
                )

    primary_records = primary.copy()
    primary_records["Model"] = primary_records["Model"].astype(str)
    primary_records["Canonical Task"] = primary_records["Canonical Task"].astype(str)
    primary_records["Primary Failure Mode"] = primary_records["Primary Failure Mode"].astype(str)

    payload = {
        "source_manifest": "/Users/justintiensmith/Downloads/Training_Data_Info (1).xlsm",
        "source_evaluations": "/Users/justintiensmith/Documents/lerobot/outputs/01a0678e-4e7e-7a31-b018-7fba72ab9fe5/Consolidated_Model_Evaluations_with_Custom_Error_Bars_Updated.xlsx",
        "complete_models": COMPLETE_MODELS,
        "task_order": TASK_ORDER,
        "mode_order": MODE_ORDER,
        "matrices": matrices,
        "matrix_cells": long_cells,
        "primary_failures": primary_records.where(pd.notna(primary_records), None).to_dict(orient="records"),
        "all_failures": all_failures.where(pd.notna(all_failures), None).to_dict(orient="records"),
        "model_counts": model_counts.to_dict(orient="index"),
        "task_counts": task_counts.to_dict(orient="index"),
        "overall_counts": overall_counts.to_dict(),
        "scope": {
            "condition": "Novel spatial grounding (Concept/compositional transfer)",
            "included_models": "GR00T Frozen LLM, Pi0.5, and MolmoAct2",
            "total_failures": int(len(primary)),
            "review_unit": "One failed rollout; one mutually exclusive primary mode per rollout",
            "caveat": "Categories are derived from qualitative rollout annotations rather than blinded video re-scoring.",
        },
    }
    PAYLOAD.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {PAYLOAD}")
    print("Overall modes:")
    print(overall_counts.to_string())


if __name__ == "__main__":
    main()
