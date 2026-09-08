from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prepare_analysis import matrix_payload


ROOT = Path(__file__).resolve().parent
SOURCE = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Spa_Bench_Manifest_and_Failure_Analysis.xlsx"
)
PAYLOAD = ROOT / "analysis_payload_reviewed.json"
CLASSIFIED_CSV = ROOT / "failure_annotations_reviewed_classified.csv"

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
    "Release/retention failure",
    "Control drift or instability",
    "Timeout or incomplete execution",
    "Other execution failure",
    "Unannotated or unclear",
]


def key(row: pd.Series) -> tuple[str, str, int, str]:
    return (
        str(row["Model"]),
        str(row["Task"]),
        int(row["Episode"]),
        str(row["Condition"]),
    )


def split_flags(value: object) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def clean_flags(primary: str, existing: object, additions: list[str], removals: list[str]) -> str:
    remove = {item.casefold() for item in removals}
    primary_equivalents = {
        "Wrong target": {"wrong target", "wrong target selected"},
        "No action": {"no action"},
        "Correct target, incorrect spatial outcome": {"incorrect spatial outcome"},
        "Grasp failure": {"grasp attempt failed"},
        "Premature release or dropped object": {"premature release/drop"},
        "Release/retention failure": {"failed to release", "release/retention failure"},
        "Control drift or instability": {"control drift/instability"},
        "Timeout or incomplete execution": {"timeout", "incomplete execution"},
    }
    remove.update(primary_equivalents.get(primary, set()))
    result: list[str] = []
    for item in [*split_flags(existing), *additions]:
        if item.casefold() in remove:
            continue
        if item not in result:
            result.append(item)
    return "; ".join(result)


# Each entry is: primary mode, confidence, classification basis, flags to add,
# and stale flags to remove. These entries cover every row that was labelled
# "Other execution failure" in the user-reviewed workbook.
REVIEWED_RECLASSIFICATIONS: dict[
    tuple[str, str, int, str], tuple[str, str, str, list[str], list[str]]
] = {
    ("VLA-0", "Physical State", 0, "In-distribution concept baseline"):
        ("Wrong target", "High", "Selected the striped cup instead of the requested white cup", ["grasp attempt failed"], []),
    ("VLA-0", "Physical State", 2, "In-distribution concept baseline"):
        ("Control drift or instability", "High", "Approached the correct cup, then drifted into empty space and contacted another cup", ["grasp attempt failed", "unintended object contact"], []),
    ("VLA-0", "Relational Placement", 6, "In-distribution concept baseline"):
        ("Wrong target", "High", "Approached the green reference pen instead of the requested blue block", ["returned home before task completion"], []),
    ("VLA-0", "Referential Description", 3, "In-distribution concept baseline"):
        ("Control drift or instability", "Medium", "The grasp trajectory drifted between candidates and contacted a non-target object", ["grasp attempt failed", "unintended object contact"], []),
    ("VLA-0", "Referential Description", 7, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Closed the gripper near the correct target without obtaining a usable grasp", ["recovery failed"], []),

    ("GR00T Frozen LLM", "Counting", 88, "Matched manipulation control"):
        ("Timeout or incomplete execution", "High", "Reached the requested goal state but did not complete the required return-to-home phase", ["goal state achieved", "incomplete return-to-home"], []),
    ("GR00T Frozen LLM", "Ordinal Position", 98, "Concept/compositional transfer"):
        ("Control drift or instability", "High", "Drifted to the workspace boundary and jittered without completing the task", ["no task-directed progress"], []),
    ("GR00T Frozen LLM", "Relational Placement", 1, "In-distribution concept baseline"):
        ("Release/retention failure", "High", "Reached the requested relation but retained the object in the gripper", ["correct spatial relation reached"], ["failed to release"]),
    ("GR00T Frozen LLM", "Relational Placement", 14, "In-distribution concept baseline"):
        ("Release/retention failure", "High", "Reached the requested relation but could not release the object", ["correct spatial relation reached"], ["failed to release", "incorrect spatial outcome"]),
    ("GR00T Frozen LLM", "Relational Placement", 20, "Concept/compositional transfer"):
        ("Release/retention failure", "High", "Reached the requested relation but did not release the object", ["correct spatial relation reached"], ["failed to release", "incorrect spatial outcome"]),
    ("GR00T Frozen LLM", "Relational Placement", 51, "Language robustness"):
        ("Release/retention failure", "High", "Retained the pen instead of setting it down at the destination", ["incorrect spatial outcome"], ["failed to release"]),
    ("GR00T Frozen LLM", "Relational Placement", 58, "Language robustness"):
        ("Release/retention failure", "High", "Retained the pen and disturbed the reference object", ["incorrect spatial outcome", "unintended object contact"], ["failed to release"]),
    ("GR00T Frozen LLM", "Relational Placement", 61, "Matched manipulation control"):
        ("Release/retention failure", "High", "Could not release the red block at the destination", [], ["failed to release"]),
    ("GR00T Frozen LLM", "Relational Placement", 64, "Concept/compositional transfer"):
        ("Release/retention failure", "High", "Continued pinching the block on the table and did not complete the return-to-home phase", ["incomplete return-to-home"], []),
    ("GR00T Frozen LLM", "Relational Placement", 86, "Concept/compositional transfer"):
        ("Timeout or incomplete execution", "High", "Reached the requested relation but did not complete the return-to-home phase", ["correct spatial relation reached", "incomplete return-to-home"], ["incorrect spatial outcome"]),
    ("GR00T Frozen LLM", "Relational Placement", 92, "Concept/compositional transfer"):
        ("Release/retention failure", "High", "Reached the requested relation but could not release the object", ["correct spatial relation reached"], ["failed to release", "incorrect spatial outcome"]),
    ("GR00T Frozen LLM", "Relational Placement", 103, "Matched manipulation control"):
        ("Release/retention failure", "High", "Moved the object toward a nearby destination but did not release it", ["incorrect spatial outcome"], ["failed to release"]),
    ("GR00T Frozen LLM", "Relational Placement", 112, "Cross-task-object directional reasoning"):
        ("Control drift or instability", "High", "Oscillated with the object in the gripper and never established a final placement", ["release/retention failure", "incorrect spatial outcome"], []),
    ("GR00T Frozen LLM", "Relational Placement", 139, "Goal already satisfied / no movement"):
        ("Control drift or instability", "High", "Repeatedly approached the object despite a no-movement instruction", ["unnecessary motion during no-movement control"], []),
    ("GR00T Frozen LLM", "Referential Description", 42, "Language robustness"):
        ("Control drift or instability", "Medium", "Approached the correct target, then deviated and could not recover", ["recovery failed"], []),
    ("GR00T Frozen LLM", "Referential Description", 47, "Language robustness"):
        ("Grasp failure", "High", "An over-tight grasp displaced the correct target off the table", ["control drift/instability", "target displaced out of reach"], []),
    ("GR00T Frozen LLM", "Referential Description", 60, "Concept/compositional transfer"):
        ("Grasp failure", "High", "Pinched the correct target and displaced it out of range instead of securing it", ["target displaced out of reach"], []),
    ("GR00T Frozen LLM", "Referential Description", 76, "Concept/compositional transfer"):
        ("Grasp failure", "High", "Over-gripping displaced the correct target before a stable grasp was established", ["target displaced out of reach", "wrong target during recovery"], []),
    ("GR00T Frozen LLM", "Referential Description", 124, "Cross-task block reasoning"):
        ("Grasp failure", "High", "Attempted the correct target but failed to obtain a usable grasp", ["control drift/instability", "recovery failed"], []),
    ("GR00T Frozen LLM", "Relative Size", 24, "Concept/compositional transfer"):
        ("Control drift or instability", "High", "Approached the correct target, then drifted to the workspace boundary", ["no task completion"], []),
    ("GR00T Frozen LLM", "Relative Size", 52, "Concept/compositional transfer"):
        ("Control drift or instability", "High", "Approached the correct target, then drifted to the workspace boundary and did not recover", ["recovery failed"], []),
    ("GR00T Frozen LLM", "Relative Size", 60, "Concept/compositional transfer"):
        ("Grasp failure", "Medium", "Failed to secure the correct target, displaced it, and switched targets during recovery", ["target displaced out of reach", "wrong target during recovery", "premature release/drop"], []),
    ("GR00T Frozen LLM", "Relative Size", 86, "Concept/compositional transfer"):
        ("Control drift or instability", "High", "Drifted to the workspace boundary without task-directed progress", ["no task-directed progress"], []),

    ("GR00T Full Fine-Tune", "Counting", 17, "In-distribution concept baseline"):
        ("Timeout or incomplete execution", "High", "Approached the correct object but returned home before completing the manipulation", ["returned home before task completion"], []),
    ("GR00T Full Fine-Tune", "Relational Placement", 14, "In-distribution concept baseline"):
        ("Wrong target", "High", "Approached the green pen instead of the requested blue block", ["grasp attempt failed", "returned home before task completion"], []),
    ("GR00T Full Fine-Tune", "Relational Placement", 15, "In-distribution concept baseline"):
        ("Wrong target", "High", "Approached the green pen instead of the requested blue block", ["grasp attempt failed", "returned home before task completion"], []),

    ("MolmoAct2", "Physical State", 134, "No valid target / no movement"):
        ("Control drift or instability", "High", "Contacted and displaced an object despite a no-movement instruction", ["unnecessary motion during no-movement control", "unintended object contact", "recovery failed"], []),
    ("MolmoAct2", "Counting", 144, "Goal already satisfied / no movement"):
        ("Control drift or instability", "High", "Repeated an approach-return cycle despite a no-movement instruction", ["unnecessary motion during no-movement control"], []),
    ("MolmoAct2", "Ordinal Position", 59, "Concept/compositional transfer"):
        ("Grasp failure", "High", "Displaced the correct target before a stable grasp and switched targets during recovery", ["target displaced out of reach", "wrong target during recovery", "recovery failed"], []),
    ("MolmoAct2", "Relational Placement", 23, "Concept/compositional transfer"):
        ("Control drift or instability", "High", "Repeated grasp-release oscillations displaced the block far outside the valid relation", ["premature release/drop", "target displaced out of reach", "incorrect spatial outcome", "recovery failed"], []),
    ("MolmoAct2", "Relational Placement", 57, "Matched manipulation control"):
        ("Release/retention failure", "High", "Reached a nearby placement but retained the object in the gripper", [], ["failed to release"]),
    ("MolmoAct2", "Relational Placement", 116, "Cross-task-object directional reasoning"):
        ("Release/retention failure", "High", "Did not release the object at the requested destination", ["control drift/instability", "incorrect spatial outcome"], ["failed to release"]),
    ("MolmoAct2", "Relational Placement", 132, "Violated-relation correction control"):
        ("Timeout or incomplete execution", "High", "Eventually grasped the correct target but never completed the requested placement", ["repeated return-to-home", "no placement completed"], []),
    ("MolmoAct2", "Referential Description", 5, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the correct target but disturbed the scene and could not complete the grasp", ["unintended object contact", "recovery failed"], []),

    ("Pi0.5", "Relational Placement", 0, "In-distribution concept baseline"):
        ("Release/retention failure", "High", "Reached the requested relation but retained the object in the gripper", ["correct spatial relation reached"], ["failed to release"]),
    ("Pi0.5", "Relational Placement", 139, "Goal already satisfied / no movement"):
        ("Control drift or instability", "High", "Repeatedly approached and pushed the object despite a no-movement instruction", ["unnecessary motion during no-movement control", "unintended object displacement"], []),
    ("Pi0.5", "Referential Description", 66, "Concept/compositional transfer"):
        ("Grasp failure", "High", "Displaced the correct target instead of securing it and could not recover", ["target displaced out of reach", "recovery failed"], []),
}


def overlay_primary_review(all_failures: pd.DataFrame, primary: pd.DataFrame) -> pd.DataFrame:
    result = all_failures.copy()
    positions = {key(row): idx for idx, row in result.iterrows()}
    editable = [
        "Observation",
        "Primary Failure Mode",
        "Secondary Flags",
        "Classification Confidence",
        "Classification Basis",
        "Needs Manual Review",
    ]
    missing: list[tuple[str, str, int, str]] = []
    for _, row in primary.iterrows():
        row_key = key(row)
        idx = positions.get(row_key)
        if idx is None:
            missing.append(row_key)
            continue
        for column in editable:
            result.at[idx, column] = row[column]
    if missing:
        raise ValueError(f"Primary-review rows missing from all-failures sheet: {missing[:5]}")
    return result


def recode_other_rows(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    current_other = result[result["Primary Failure Mode"].eq("Other execution failure")]
    actual = {key(row) for _, row in current_other.iterrows()}
    expected = set(REVIEWED_RECLASSIFICATIONS)
    if actual != expected:
        raise ValueError(
            "The reviewed workbook's current Other rows differ from the audited map. "
            f"Missing mappings: {sorted(actual - expected)}; stale mappings: {sorted(expected - actual)}"
        )

    positions = {key(row): idx for idx, row in result.iterrows()}
    for row_key, (mode, confidence, basis, additions, removals) in REVIEWED_RECLASSIFICATIONS.items():
        idx = positions[row_key]
        result.at[idx, "Primary Failure Mode"] = mode
        result.at[idx, "Secondary Flags"] = clean_flags(
            mode, result.at[idx, "Secondary Flags"], additions, removals
        )
        result.at[idx, "Classification Confidence"] = confidence
        result.at[idx, "Classification Basis"] = basis
        result.at[idx, "Needs Manual Review"] = "No"
    return result


def main() -> None:
    all_failures = pd.read_excel(SOURCE, sheet_name="All Classified Failures", header=2)
    primary_review = pd.read_excel(SOURCE, sheet_name="Primary Failures", header=2)
    all_failures = overlay_primary_review(all_failures, primary_review)
    all_failures = recode_other_rows(all_failures)
    all_failures["Canonical Task"] = all_failures["Task"]
    all_failures.to_csv(CLASSIFIED_CSV, index=False)

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
        .size().unstack(fill_value=0)
        .reindex(index=COMPLETE_MODELS, columns=MODE_ORDER, fill_value=0)
    )
    task_counts = (
        primary.groupby(["Canonical Task", "Primary Failure Mode"], observed=False)
        .size().unstack(fill_value=0)
        .reindex(index=TASK_ORDER, columns=MODE_ORDER, fill_value=0)
    )
    overall_counts = primary["Primary Failure Mode"].value_counts().reindex(MODE_ORDER, fill_value=0)

    matrices = matrix_payload()
    long_cells: list[dict] = []
    for matrix in matrices:
        for row_name, row_values in zip(matrix["rows"], matrix["values"]):
            for col_name, status in zip(matrix["columns"], row_values):
                long_cells.append({
                    "Task": matrix["task"],
                    "Context": matrix["context"],
                    "Concept": row_name,
                    "Argument": col_name.replace("\n", " "),
                    "Status": status,
                })

    primary_records = primary.copy()
    for column in ["Model", "Canonical Task", "Primary Failure Mode"]:
        primary_records[column] = primary_records[column].astype(str)

    payload = {
        "source_manifest": "Training_Data_Info (1).xlsm",
        "source_evaluations": "Spa_Bench_Manifest_and_Failure_Analysis.xlsx (user-reviewed source)",
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
            "caveat": "Categories are derived from reviewed qualitative rollout annotations rather than blinded video re-scoring.",
        },
    }
    PAYLOAD.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {PAYLOAD}")
    print(f"Wrote {CLASSIFIED_CSV}")
    print("\nPrimary failure modes:")
    print(overall_counts.to_string())
    print("\nPrimary failure modes by model:")
    print(model_counts.to_string())
    print("\nPrimary failure modes by task:")
    print(task_counts.to_string())


if __name__ == "__main__":
    main()
