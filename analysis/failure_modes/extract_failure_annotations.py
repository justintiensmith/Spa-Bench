from pathlib import Path

import pandas as pd


WORKBOOK = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Consolidated_Model_Evaluations_with_Custom_Error_Bars_Updated.xlsx"
)
OUTPUT = Path("failure_annotations_raw.csv")

MODEL_SHEETS = {
    "VLA-0": "VLA-0",
    "GR00T Frozen LLM": "GR00T Vision",
    "GR00T Full Fine-Tune": "GR00T Full",
    "MolmoAct2": "MolmoAct2",
    "Pi0.5": "Pi0.5",
}

frames = []
for model, sheet in MODEL_SHEETS.items():
    frame = pd.read_excel(WORKBOOK, sheet_name=sheet)
    frame = frame[frame["Status"].astype(str).str.strip().str.casefold() == "failure"].copy()
    frame.insert(0, "Model", model)
    keep = [
        "Model",
        "Task",
        "Episode",
        "Condition",
        "Comparison / Subtype",
        "Prompt",
        "Expected Target / Action",
        "Observations",
    ]
    frames.append(frame[keep])

out = pd.concat(frames, ignore_index=True)
out.to_csv(OUTPUT, index=False)
print(f"wrote {len(out)} failures to {OUTPUT}")
print("\nTop recurring annotations:")
counts = (
    out.assign(Observations=out["Observations"].fillna("").astype(str).str.strip().str.casefold())
    .groupby("Observations")
    .size()
    .sort_values(ascending=False)
)
print(counts.head(250).to_string())
