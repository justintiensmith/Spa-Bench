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
OUTPUT = Path(__file__).resolve().parent / "model_failure_chart_data.json"

MODEL_ORDER = [
    "VLA-0",
    "GR00T Full Fine-Tune",
    "GR00T Frozen LLM",
    "Pi0.5",
    "MolmoAct2",
]

MODE_ORDER = [
    "Wrong target",
    "No action",
    "Unnecessary intervention",
    "Grasp failure",
    "Correct target, incorrect spatial outcome",
    "Timeout or incomplete execution",
    "Premature release or dropped object",
    "Control drift or instability",
    "Release/retention failure",
]


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denominator
    return max(0.0, center - half), min(1.0, center + half)


data = pd.read_excel(SOURCE, sheet_name="All Classified Failures", header=2)
required = {"Model", "Primary Failure Mode"}
if not required.issubset(data.columns):
    raise ValueError(f"Missing required columns: {required - set(data.columns)}")
if data["Model"].isna().any() or data["Primary Failure Mode"].isna().any():
    raise ValueError("All failed rollouts must have a model and primary failure mode.")

unknown_models = sorted(set(data["Model"]) - set(MODEL_ORDER))
unknown_modes = sorted(set(data["Primary Failure Mode"]) - set(MODE_ORDER))
if unknown_models:
    raise ValueError(f"Unexpected models: {unknown_models}")
if unknown_modes:
    raise ValueError(f"Unexpected primary failure modes: {unknown_modes}")

rows = []
for model in MODEL_ORDER:
    model_data = data[data["Model"].eq(model)]
    total = len(model_data)
    for mode in MODE_ORDER:
        count = int(model_data["Primary Failure Mode"].eq(mode).sum())
        share = count / total
        lower, upper = wilson(count, total)
        rows.append(
            {
                "Model": model,
                "Failure Mode": mode,
                "Count": count,
                "Model Failures": total,
                "Share": share,
                "CI Lower": lower,
                "CI Upper": upper,
                "Lower Error": share - lower,
                "Upper Error": upper - share,
            }
        )

totals = data.groupby("Model").size().to_dict()
if sum(totals.values()) != len(data):
    raise AssertionError("Model totals do not reconcile to all classified failures.")
for model in MODEL_ORDER:
    if sum(row["Count"] for row in rows if row["Model"] == model) != totals[model]:
        raise AssertionError(f"Failure-mode counts do not reconcile for {model}.")

payload = {
    "scope": "All failed rollouts across every task and evaluation condition",
    "total_failures": len(data),
    "model_order": MODEL_ORDER,
    "failure_mode_order": MODE_ORDER,
    "model_totals": totals,
    "rows": rows,
}
OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"total_failures": len(data), "model_totals": totals}, indent=2))
