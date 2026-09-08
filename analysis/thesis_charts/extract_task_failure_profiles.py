from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


SOURCE = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Spa_Bench_All_Failure_Audit.xlsx"
)
OUTPUT = Path(__file__).resolve().parent / "task_failure_profile_data.json"

CONDITIONS = {
    "Novel Spatial Grounding": "Concept/compositional transfer",
    "Familiar Spatial Grounding": "In-distribution concept baseline",
}
TASK_ORDER = [
    "Counting",
    "Ordinal Position",
    "Relational Placement",
    "Physical State",
    "Relative Size",
    "Referential Description",
]
MODEL_ORDER = {
    "Novel Spatial Grounding": ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"],
    "Familiar Spatial Grounding": [
        "VLA-0",
        "GR00T Full Fine-Tune",
        "GR00T Frozen LLM",
        "Pi0.5",
        "MolmoAct2",
    ],
}
FAILURE_MODE_ORDER = [
    "Wrong target",
    "No action",
    "Grasp failure",
    "Correct target, incorrect spatial outcome",
    "Timeout or incomplete execution",
    "Premature release or dropped object",
    "Control drift or instability",
    "Release/retention failure",
]


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    proportion = successes / trials
    denominator = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / denominator
    half_width = (
        z
        * math.sqrt((proportion * (1 - proportion) + z * z / (4 * trials)) / trials)
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


data = pd.read_excel(SOURCE, sheet_name="All Classified Failures", header=2)
required = {"Model", "Task", "Condition", "Primary Failure Mode"}
if not required.issubset(data.columns):
    raise ValueError(f"Missing required columns: {required - set(data.columns)}")

selected = data[data["Condition"].isin(CONDITIONS.values())].copy()
if selected[list(required)].isna().any().any():
    raise ValueError("Every selected failed rollout must have complete grouping fields.")

unexpected_tasks = sorted(set(selected["Task"]) - set(TASK_ORDER))
unexpected_modes = sorted(set(selected["Primary Failure Mode"]) - set(FAILURE_MODE_ORDER))
if unexpected_tasks:
    raise ValueError(f"Unexpected task names: {unexpected_tasks}")
if unexpected_modes:
    raise ValueError(f"Unexpected failure modes: {unexpected_modes}")

rows: list[dict] = []
condition_totals: dict[str, int] = {}
task_model_totals: dict[str, dict[str, dict[str, int]]] = {}
for display_condition, source_condition in CONDITIONS.items():
    condition_data = selected[selected["Condition"].eq(source_condition)]
    condition_totals[display_condition] = len(condition_data)
    task_model_totals[display_condition] = {}
    expected_models = set(MODEL_ORDER[display_condition])
    actual_models = set(condition_data["Model"])
    if actual_models != expected_models:
        raise ValueError(
            f"Unexpected model coverage for {display_condition}: "
            f"expected {sorted(expected_models)}, found {sorted(actual_models)}"
        )

    for task in TASK_ORDER:
        task_model_totals[display_condition][task] = {}
        for model in MODEL_ORDER[display_condition]:
            group = condition_data[
                condition_data["Task"].eq(task) & condition_data["Model"].eq(model)
            ]
            total = len(group)
            if total == 0:
                raise ValueError(f"No classified failures for {display_condition}, {task}, {model}")
            task_model_totals[display_condition][task][model] = total
            for mode in FAILURE_MODE_ORDER:
                count = int(group["Primary Failure Mode"].eq(mode).sum())
                share = count / total
                lower, upper = wilson(count, total)
                rows.append(
                    {
                        "Condition": display_condition,
                        "Task": task,
                        "Model": model,
                        "Failure Mode": mode,
                        "Count": count,
                        "Task-Model Failures": total,
                        "Share": share,
                        "CI Lower": lower,
                        "CI Upper": upper,
                        "Lower Error": share - lower,
                        "Upper Error": upper - share,
                    }
                )

    reconciled = sum(
        task_model_totals[display_condition][task][model]
        for task in TASK_ORDER
        for model in MODEL_ORDER[display_condition]
    )
    if reconciled != len(condition_data):
        raise AssertionError(f"Condition total does not reconcile for {display_condition}.")

if sum(condition_totals.values()) != len(selected):
    raise AssertionError("Selected condition totals do not reconcile.")

payload = {
    "source_sheet": "All Classified Failures",
    "condition_mapping": CONDITIONS,
    "condition_totals": condition_totals,
    "task_order": TASK_ORDER,
    "model_order": MODEL_ORDER,
    "failure_mode_order": FAILURE_MODE_ORDER,
    "task_model_totals": task_model_totals,
    "rows": rows,
}
OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "condition_totals": condition_totals,
            "task_model_totals": task_model_totals,
            "rows": len(rows),
        },
        indent=2,
    )
)
