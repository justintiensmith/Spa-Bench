from pathlib import Path

import pandas as pd


WORKBOOK = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Consolidated_Model_Evaluations_with_Custom_Error_Bars_Updated.xlsx"
)

MODEL_SHEETS = {
    "VLA-0": "VLA-0",
    "GR00T Frozen LLM": "GR00T Vision",
    "GR00T Full Fine-Tune": "GR00T Full",
    "MolmoAct2": "MolmoAct2",
    "Pi0.5": "Pi0.5",
}

for model, sheet in MODEL_SHEETS.items():
    frame = pd.read_excel(WORKBOOK, sheet_name=sheet)
    failures = frame[frame["Status"].astype(str).str.strip().str.casefold() == "failure"].copy()
    annotations = failures["Observations"].fillna("").astype(str).str.strip()
    print(f"\n### {model}")
    print(f"rows={len(frame)} failures={len(failures)} annotated={annotations.ne('').sum()} blank={annotations.eq('').sum()}")
    print("by task")
    print(failures.groupby("Task").size().sort_values(ascending=False).to_string())
    print("sample annotations")
    for text in annotations[annotations.ne("")].head(40):
        print("-", text.replace("\n", " ")[:280])
