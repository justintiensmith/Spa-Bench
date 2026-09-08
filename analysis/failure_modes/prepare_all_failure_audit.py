from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prepare_analysis import matrix_payload


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "failure_annotations_reviewed_classified.csv"
OUTPUT_CSV = ROOT / "failure_annotations_all_audited.csv"
PAYLOAD = ROOT / "analysis_payload_all_audited.json"

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
    "Unnecessary intervention",
    "Other execution failure",
    "Unannotated or unclear",
]
NO_MOVEMENT_CONDITIONS = {
    "Goal already satisfied / no movement",
    "Invalid ordinal / no-movement diagnostic",
    "No valid candidate category / no movement",
    "No valid target / no movement",
}


def row_key(row: pd.Series) -> tuple[str, str, int, str]:
    return str(row["Model"]), str(row["Task"]), int(row["Episode"]), str(row["Condition"])


def split_flags(value: object) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def merged_flags(primary: str, existing: object, additions: list[str]) -> str:
    primary_equivalents = {
        "Wrong target": {"wrong target", "wrong target selected"},
        "No action": {"no action", "no task-directed progress"},
        "Correct target, incorrect spatial outcome": {"incorrect spatial outcome"},
        "Grasp failure": {"grasp attempt failed"},
        "Premature release or dropped object": {"premature release/drop"},
        "Release/retention failure": {"failed to release", "release/retention failure"},
        "Control drift or instability": {"control drift/instability"},
        "Timeout or incomplete execution": {"timeout", "incomplete execution"},
        "Unnecessary intervention": {"unnecessary motion during no-movement control"},
    }
    remove = {item.casefold() for item in primary_equivalents.get(primary, set())}
    result: list[str] = []
    for item in [*split_flags(existing), *additions]:
        if item.casefold() in remove:
            continue
        if item not in result:
            result.append(item)
    return "; ".join(result)


# Suggested classifications for every nonblank annotation that remained unclear.
# The final Boolean marks rows where the language is still ambiguous enough that
# the user should confirm the label.
REVIEWED_UNCLEAR: dict[
    tuple[str, str, int, str], tuple[str, str, str, list[str], bool]
] = {
    ("VLA-0", "Physical State", 4, "In-distribution concept baseline"):
        ("Wrong target", "High", "Approached the open glass container rather than the requested brown cup.", ["grasp attempt failed"], False),
    ("VLA-0", "Counting", 1, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the blue pen but did not open the gripper to grasp it.", [], False),
    ("VLA-0", "Counting", 2, "In-distribution concept baseline"):
        ("Grasp failure", "Medium", "The annotation describes an unsuccessful gripping motion, but the intended target is not explicit.", [], True),
    ("VLA-0", "Ordinal Position", 3, "In-distribution concept baseline"):
        ("Control drift or instability", "Medium", "Moved into the middle of the workspace without a clear target-directed grasp.", [], True),
    ("VLA-0", "Ordinal Position", 8, "In-distribution concept baseline"):
        ("Wrong target", "Medium", "The annotation suggests an approach to green rather than the requested blue object, but is equivocal.", [], True),
    ("VLA-0", "Relational Placement", 0, "In-distribution concept baseline"):
        ("Wrong target", "High", "Approached the red block rather than the requested green pen.", ["grasp attempt failed"], False),
    ("VLA-0", "Relational Placement", 2, "In-distribution concept baseline"):
        ("Wrong target", "High", "Approached the red object rather than the requested pink marker.", [], False),
    ("VLA-0", "Relational Placement", 5, "In-distribution concept baseline"):
        ("Unannotated or unclear", "Low", "The note only references a previous trajectory and does not uniquely identify this rollout's failure.", [], True),
    ("VLA-0", "Relational Placement", 9, "In-distribution concept baseline"):
        ("Wrong target", "High", "Approached the blue block rather than the requested red block.", [], False),
    ("VLA-0", "Referential Description", 2, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Reached the correct Coke can but did not close the gripper before the rollout ended.", ["late task initiation"], False),
    ("VLA-0", "Referential Description", 4, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Used the correct target strategy but did not obtain a usable grasp.", [], False),
    ("VLA-0", "Relative Size", 6, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the requested juggling ball but could not grasp it.", [], False),
    ("VLA-0", "Relative Size", 11, "In-distribution concept baseline"):
        ("Grasp failure", "Medium", "Attempted the requested can but did not secure it.", [], False),
    ("VLA-0", "Relative Size", 15, "In-distribution concept baseline"):
        ("Control drift or instability", "Medium", "The trajectory did not rotate far enough and deviated toward the sharpener.", ["grasp attempt failed"], True),
    ("VLA-0", "Relative Size", 17, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the green block but did not open the gripper.", [], False),
    ("VLA-0", "Relative Size", 19, "In-distribution concept baseline"):
        ("Grasp failure", "Medium", "The motion remained between two candidates and never produced a usable grasp.", ["control drift/instability"], True),

    ("GR00T Frozen LLM", "Physical State", 38, "Language robustness"):
        ("Wrong target", "High", "Selected the open cup instead of the requested closed brown cup.", [], False),
    ("GR00T Frozen LLM", "Physical State", 126, "Novel-object state reasoning"):
        ("Wrong target", "High", "Attempted the closed white cup instead of the requested black cup.", ["grasp attempt failed"], False),
    ("GR00T Frozen LLM", "Counting", 5, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the yellow object but could not grasp it.", [], False),
    ("GR00T Frozen LLM", "Counting", 44, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Attempted to remove an object even though the requested count was already satisfied.", ["grasp attempt failed"], False),
    ("GR00T Frozen LLM", "Counting", 45, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Approached the bowl despite the no-movement requirement.", [], False),
    ("GR00T Frozen LLM", "Counting", 48, "Matched manipulation control"):
        ("Grasp failure", "High", "Attempted the requested airplane toy but did not remove it.", [], False),
    ("GR00T Frozen LLM", "Counting", 80, "Cross-task object reasoning"):
        ("Grasp failure", "High", "Repeatedly pinched at the highlighter without securing it.", ["control drift/instability"], False),
    ("GR00T Frozen LLM", "Counting", 98, "Matched manipulation control"):
        ("Grasp failure", "High", "Attempted the requested yellow object but failed to remove it.", [], False),
    ("GR00T Frozen LLM", "Ordinal Position", 145, "Invalid ordinal / no-movement diagnostic"):
        ("Unnecessary intervention", "High", "Attempted the green object despite an invalid-ordinal no-movement instruction.", ["grasp attempt failed"], False),
    ("GR00T Frozen LLM", "Relational Placement", 46, "Language robustness"):
        ("Correct target, incorrect spatial outcome", "Medium", "The object ended leaning to the right rather than clearly in front; the final relation is somewhat ambiguous.", [], True),
    ("GR00T Frozen LLM", "Relational Placement", 117, "Cross-task-object directional reasoning"):
        ("Control drift or instability", "High", "Repeated grasp-release oscillation prevented a completed placement.", ["premature release/drop", "no placement completed"], False),
    ("GR00T Frozen LLM", "Relational Placement", 123, "Cross-task-object directional reasoning"):
        ("Wrong target", "High", "Selected the pink marker instead of the requested ball.", ["control drift/instability"], False),
    ("GR00T Frozen LLM", "Relational Placement", 124, "Cross-task-object directional reasoning"):
        ("Timeout or incomplete execution", "High", "Grasped the correct red object but did not execute the requested placement.", [], False),
    ("GR00T Frozen LLM", "Referential Description", 67, "Matched manipulation control"):
        ("Grasp failure", "High", "Pinched the requested Coke can and displaced it without securing it.", ["target displaced out of reach"], False),
    ("GR00T Frozen LLM", "Referential Description", 79, "Matched manipulation control"):
        ("Grasp failure", "High", "Pinched the requested Pepsi can out of reach without securing it.", ["target displaced out of reach"], False),
    ("GR00T Frozen LLM", "Referential Description", 149, "No valid candidate category / no movement"):
        ("Unnecessary intervention", "High", "Attempted the airplane toy despite the no-valid-candidate instruction.", ["wrong-object selection", "grasp attempt failed"], False),
    ("GR00T Frozen LLM", "Relative Size", 3, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the requested Pepsi can but did not close the gripper.", [], False),
    ("GR00T Frozen LLM", "Relative Size", 113, "Cross-task airplane counterfactual"):
        ("Grasp failure", "High", "The note indicates correct target reasoning but an unsuccessful grasp of the requested can.", [], False),

    ("GR00T Full Fine-Tune", "Counting", 6, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the bowl but did not successfully remove an object.", [], False),
    ("GR00T Full Fine-Tune", "Counting", 11, "In-distribution concept baseline"):
        ("Timeout or incomplete execution", "High", "Approached the correct yellow object, then returned home before removing it.", [], False),
    ("GR00T Full Fine-Tune", "Relational Placement", 3, "In-distribution concept baseline"):
        ("Timeout or incomplete execution", "High", "Turned toward the correct pink object but did not begin the placement.", [], False),
    ("GR00T Full Fine-Tune", "Relational Placement", 5, "In-distribution concept baseline"):
        ("Wrong target", "High", "Selected the pink object instead of the requested green pen.", ["incorrect spatial outcome"], False),
    ("GR00T Full Fine-Tune", "Relative Size", 17, "In-distribution concept baseline"):
        ("Wrong target", "High", "Moved from the requested green block toward the juggling ball.", ["control drift/instability"], False),

    ("MolmoAct2", "Counting", 121, "Cross-task object reasoning"):
        ("Timeout or incomplete execution", "High", "Initiated too late and did not remove the requested highlighter.", [], False),
    ("MolmoAct2", "Relational Placement", 4, "In-distribution concept baseline"):
        ("Correct target, incorrect spatial outcome", "High", "Placed the object primarily to the left rather than in front.", [], False),
    ("MolmoAct2", "Relational Placement", 129, "Cross-task-object directional reasoning"):
        ("No action", "High", "Did not initiate task-directed motion.", [], False),
    ("MolmoAct2", "Relational Placement", 134, "Violated-relation correction control"):
        ("Timeout or incomplete execution", "High", "Approached the correct green object but did not perform the corrective placement.", [], False),
    ("MolmoAct2", "Relational Placement", 135, "Violated-relation correction control"):
        ("Timeout or incomplete execution", "High", "Approached the correct pink object but did not perform the corrective placement.", [], False),
    ("MolmoAct2", "Relational Placement", 136, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Repeatedly approached and nudged an object despite a no-movement instruction.", ["unintended object contact"], False),
    ("MolmoAct2", "Relational Placement", 138, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Approached an object and moved it despite a no-movement instruction.", ["unintended object displacement"], False),
    ("MolmoAct2", "Relational Placement", 139, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Repeatedly approached the scene despite a no-movement instruction.", [], False),
    ("MolmoAct2", "Relational Placement", 147, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Repeatedly approached an object despite a no-movement instruction.", [], False),
    ("MolmoAct2", "Relational Placement", 148, "Violated-relation correction control"):
        ("Timeout or incomplete execution", "High", "Approached the correct red object but did not perform the corrective placement.", [], False),
    ("MolmoAct2", "Relational Placement", 149, "Violated-relation correction control"):
        ("Timeout or incomplete execution", "High", "Approached the correct blue object but did not perform the corrective placement.", [], False),
    ("MolmoAct2", "Referential Description", 42, "Language robustness"):
        ("Wrong target", "High", "Selected the sharpener rather than the requested referential target.", [], False),

    ("Pi0.5", "Physical State", 46, "Language robustness"):
        ("Wrong target", "High", "Selected an open object instead of the requested closed object.", [], False),
    ("Pi0.5", "Physical State", 49, "Matched manipulation control"):
        ("Grasp failure", "High", "Failed to secure the requested spice container, then drifted toward the brown cup.", ["control drift/instability", "wrong target during recovery"], False),
    ("Pi0.5", "Physical State", 138, "No valid target / no movement"):
        ("Unnecessary intervention", "High", "Intervened in the scene despite the no-valid-target instruction.", [], False),
    ("Pi0.5", "Physical State", 139, "No valid target / no movement"):
        ("Unnecessary intervention", "High", "Intervened in the scene despite the no-valid-target instruction.", [], False),
    ("Pi0.5", "Physical State", 140, "No valid target / no movement"):
        ("Unnecessary intervention", "High", "Intervened in the scene despite the no-valid-target instruction.", [], False),
    ("Pi0.5", "Counting", 6, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the yellow object but failed to grasp it.", [], False),
    ("Pi0.5", "Counting", 12, "In-distribution concept baseline"):
        ("Grasp failure", "High", "Approached the airplane toy but failed to grasp it.", [], False),
    ("Pi0.5", "Counting", 27, "Matched manipulation control"):
        ("Grasp failure", "High", "Attempted the requested blue object but failed to remove it.", [], False),
    ("Pi0.5", "Counting", 45, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Attempted a grasp despite the no-movement requirement.", ["grasp attempt failed"], False),
    ("Pi0.5", "Counting", 69, "Matched manipulation control"):
        ("Grasp failure", "High", "Failed to grasp the requested yellow object, then selected blue during recovery.", ["wrong target during recovery"], False),
    ("Pi0.5", "Counting", 118, "Cross-task object reasoning"):
        ("Timeout or incomplete execution", "High", "Started too late to complete removal of the requested yellow object.", [], False),
    ("Pi0.5", "Ordinal Position", 146, "Invalid ordinal / no-movement diagnostic"):
        ("Unnecessary intervention", "High", "Attempted a grasp despite the invalid-ordinal no-movement instruction.", ["grasp attempt failed"], False),
    ("Pi0.5", "Ordinal Position", 147, "Invalid ordinal / no-movement diagnostic"):
        ("Unnecessary intervention", "High", "Attempted a grasp despite the invalid-ordinal no-movement instruction.", ["grasp attempt failed"], False),
    ("Pi0.5", "Relational Placement", 114, "Cross-task-object directional reasoning"):
        ("Correct target, incorrect spatial outcome", "Medium", "The note reports a left placement rather than the requested relation; target identity is not fully explicit.", [], True),
    ("Pi0.5", "Relational Placement", 134, "Violated-relation correction control"):
        ("Timeout or incomplete execution", "High", "Approached the correct green object but did not perform the corrective placement.", [], False),
    ("Pi0.5", "Relational Placement", 151, "Violated-relation correction control"):
        ("Timeout or incomplete execution", "High", "Approached the correct pink object but did not perform the corrective placement.", [], False),
    ("Pi0.5", "Relational Placement", 161, "Goal already satisfied / no movement"):
        ("Unnecessary intervention", "High", "Approached the pink object twice despite the no-movement instruction.", [], False),
}


def apply_no_movement_rule(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    mask = result["Condition"].isin(NO_MOVEMENT_CONDITIONS)
    for idx in result.index[mask]:
        old_primary = str(result.at[idx, "Primary Failure Mode"])
        note = result.at[idx, "Observation"]
        has_note = pd.notna(note) and bool(str(note).strip())
        flag_map = {
            "Wrong target": ["object selected despite no-movement instruction"],
            "Grasp failure": ["grasp attempt failed"],
            "Correct target, incorrect spatial outcome": ["scene altered despite no-movement instruction"],
            "Premature release or dropped object": ["premature release/drop"],
            "Release/retention failure": ["release/retention failure"],
            "Control drift or instability": ["control drift/instability"],
            "Timeout or incomplete execution": ["timeout/incomplete execution"],
        }
        result.at[idx, "Primary Failure Mode"] = "Unnecessary intervention"
        result.at[idx, "Secondary Flags"] = merged_flags(
            "Unnecessary intervention", result.at[idx, "Secondary Flags"], flag_map.get(old_primary, [])
        )
        result.at[idx, "Classification Confidence"] = "High" if has_note else "Medium"
        result.at[idx, "Classification Basis"] = (
            "The failed no-movement control included task-directed motion or a scene change."
            if has_note
            else "A failed no-movement control implies an intervention, but the qualitative note is missing."
        )
        result.at[idx, "Needs Manual Review"] = "No" if has_note else "Yes"
    return result


def apply_annotated_review(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    positions = {row_key(row): idx for idx, row in result.iterrows()}
    unresolved = result[
        result["Primary Failure Mode"].eq("Unannotated or unclear")
        & result["Observation"].notna()
        & result["Observation"].astype(str).str.strip().ne("")
    ]
    actual = {row_key(row) for _, row in unresolved.iterrows()}
    expected = set(REVIEWED_UNCLEAR)
    if actual != expected:
        raise ValueError(
            "The nonblank unclear rows differ from the audit map. "
            f"Missing mappings: {sorted(actual - expected)}; stale mappings: {sorted(expected - actual)}"
        )
    for key, (mode, confidence, basis, additions, needs_review) in REVIEWED_UNCLEAR.items():
        idx = positions[key]
        result.at[idx, "Primary Failure Mode"] = mode
        result.at[idx, "Secondary Flags"] = merged_flags(
            mode, result.at[idx, "Secondary Flags"], additions
        )
        result.at[idx, "Classification Confidence"] = confidence
        result.at[idx, "Classification Basis"] = basis
        result.at[idx, "Needs Manual Review"] = "Yes" if needs_review else "No"
    return result


def accept_user_reviewed_labels(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    mask = (
        result["Needs Manual Review"].eq("Yes")
        & result["Observation"].notna()
        & result["Primary Failure Mode"].ne("Unannotated or unclear")
        & result["Classification Confidence"].eq("Low")
    )
    for idx in result.index[mask]:
        mode = str(result.at[idx, "Primary Failure Mode"])
        result.at[idx, "Classification Confidence"] = "High"
        result.at[idx, "Classification Basis"] = (
            "The user-reviewed annotation explicitly reports no task-directed motion."
            if mode == "No action"
            else "The user-reviewed annotation explicitly identifies a non-target object."
        )
        result.at[idx, "Needs Manual Review"] = "No"
    return result


def make_review_queue(data: pd.DataFrame) -> pd.DataFrame:
    queue = data[data["Needs Manual Review"].eq("Yes")].copy()
    queue["Why Review Needed"] = queue.apply(
        lambda row: (
            "Qualitative observation is missing; inspect the rollout and add a note."
            if pd.isna(row["Observation"]) or not str(row["Observation"]).strip()
            else "Annotation supports a provisional label but remains ambiguous; confirm against the rollout."
        ),
        axis=1,
    )
    return queue


def main() -> None:
    data = pd.read_csv(SOURCE)
    if len(data) != 1367:
        raise ValueError(f"Expected 1,367 failed rollouts, found {len(data)}")
    data = accept_user_reviewed_labels(data)
    data = apply_annotated_review(data)
    data = apply_no_movement_rule(data)
    data["Canonical Task"] = data["Task"]
    data.to_csv(OUTPUT_CSV, index=False)

    primary = data[
        data["Model"].isin(COMPLETE_MODELS)
        & data["Condition"].eq("Concept/compositional transfer")
    ].copy()
    primary["Model"] = pd.Categorical(primary["Model"], COMPLETE_MODELS, ordered=True)
    primary["Canonical Task"] = pd.Categorical(primary["Canonical Task"], TASK_ORDER, ordered=True)
    primary["Primary Failure Mode"] = pd.Categorical(primary["Primary Failure Mode"], MODE_ORDER, ordered=True)
    primary = primary.sort_values(["Model", "Canonical Task", "Episode"])

    review_queue = make_review_queue(data)
    blank_notes = data["Observation"].isna() | data["Observation"].astype(str).str.strip().eq("")
    residual_unclear = data["Primary Failure Mode"].eq("Unannotated or unclear")

    matrices = matrix_payload()
    long_cells: list[dict] = []
    for matrix in matrices:
        for concept, values in zip(matrix["rows"], matrix["values"]):
            for argument, status in zip(matrix["columns"], values):
                long_cells.append({
                    "Task": matrix["task"],
                    "Context": matrix["context"],
                    "Concept": concept,
                    "Argument": argument.replace("\n", " "),
                    "Status": status,
                })

    primary_records = primary.copy()
    for column in ["Model", "Canonical Task", "Primary Failure Mode"]:
        primary_records[column] = primary_records[column].astype(str)
    condition_order = sorted(data["Condition"].dropna().astype(str).unique())

    payload = {
        "source_manifest": "Training_Data_Info (1).xlsm",
        "source_evaluations": "Spa_Bench_Manifest_and_Failure_Analysis.xlsx plus the user's latest annotation review",
        "complete_models": COMPLETE_MODELS,
        "task_order": TASK_ORDER,
        "mode_order": MODE_ORDER,
        "condition_order": condition_order,
        "matrices": matrices,
        "matrix_cells": long_cells,
        "primary_failures": json.loads(primary_records.to_json(orient="records")),
        "all_failures": json.loads(data.to_json(orient="records")),
        "review_queue": json.loads(review_queue.to_json(orient="records")),
        "scope": {
            "condition": "Novel spatial grounding (Concept/compositional transfer)",
            "included_models": "GR00T Frozen LLM, Pi0.5, and MolmoAct2",
            "total_failures": int(len(primary)),
            "all_failures": int(len(data)),
            "review_queue": int(len(review_queue)),
            "missing_observations": int(blank_notes.sum()),
            "ambiguous_nonblank": int((review_queue["Observation"].notna() & review_queue["Observation"].astype(str).str.strip().ne("")).sum()),
            "residual_unclear": int(residual_unclear.sum()),
            "unnecessary_interventions": int(data["Primary Failure Mode"].eq("Unnecessary intervention").sum()),
            "review_unit": "One failed rollout; one mutually exclusive primary mode per rollout",
            "caveat": "Categories are derived from qualitative rollout annotations rather than independent blinded video re-scoring.",
        },
    }
    PAYLOAD.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {OUTPUT_CSV}")
    print(f"Wrote {PAYLOAD}")
    print("\nAll-failure primary modes:")
    print(data["Primary Failure Mode"].value_counts().reindex(MODE_ORDER, fill_value=0).to_string())
    print("\nAudit queue:")
    print(review_queue[["Model", "Task", "Episode", "Condition", "Primary Failure Mode", "Why Review Needed"]].to_string(index=False))
    print("\nPrimary novel-spatial failure modes:")
    print(primary["Primary Failure Mode"].value_counts().reindex(MODE_ORDER, fill_value=0).to_string())


if __name__ == "__main__":
    main()
