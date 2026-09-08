from pathlib import Path

import pandas as pd


WORKBOOK = Path("/Users/justintiensmith/Downloads/Training_Data_Info (1).xlsm")
frame = pd.read_excel(WORKBOOK, sheet_name="Prompt Manifest", header=2)

print(frame.groupby("Task").size().to_string())
for task in frame["Task"].dropna().unique():
    block = frame[frame["Task"] == task]
    print(f"\n### {task} ({len(block)})")
    print("roles")
    print(block["Training Role"].value_counts(dropna=False).to_string())
    print("factors")
    print(block["Factor Key"].value_counts(dropna=False).to_string())
    cols = [
        "Episode",
        "Training Prompt",
        "Training Role",
        "Explicit Concept / Output",
        "Factor Key",
        "Held-Out Composition",
        "Target Object",
        "Sequence Length (Ordering Only)",
    ]
    print(block[cols].head(12).to_string(index=False))
