from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


SOURCE = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Spa_Bench_All_Failure_Audit.xlsx"
)
OUT = Path(__file__).resolve().parent / "failure_chart_data.json"


def load_summary(sheet_name: str, scope: str) -> dict:
    frame = pd.read_excel(SOURCE, sheet_name=sheet_name, header=3)
    frame = frame[pd.to_numeric(frame["Count"], errors="coerce").notna()].copy()
    frame = frame[pd.to_numeric(frame["Share of Failures"], errors="coerce").notna()].copy()
    frame["Count"] = frame["Count"].astype(int)
    frame = frame[frame["Count"].gt(0)]
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "Failure Mode": str(row["Failure Mode"]),
                "Count": int(row["Count"]),
                "Share": float(row["Share of Failures"]),
                "CI Lower": float(row["Wilson 95% Lower"]),
                "CI Upper": float(row["Wilson 95% Upper"]),
            }
        )
    total = sum(row["Count"] for row in rows)
    return {"scope": scope, "total": total, "rows": rows}


payload = {
    "Novel": load_summary(
        "Failure Summary",
        "Novel spatial grounding failures across the three fully evaluated models",
    ),
    "All": load_summary(
        "All Failure Summary",
        "All failed rollouts across every evaluation condition and model",
    ),
}
OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload, indent=2))
