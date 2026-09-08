from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Consolidated_Model_Evaluations_with_Custom_Error_Bars_Updated.xlsx"
)
SHEETS = ["GR00T Vision", "MolmoAct2", "Pi0.5"]


def main() -> None:
    for sheet in SHEETS:
        frame = pd.read_excel(SOURCE, sheet_name=sheet)
        frame = frame[frame["Status"].isin(["Success", "Failure"])].copy()
        print(f"\n### {sheet}: {len(frame)} scored")
        print("Conditions:")
        print(frame.groupby(["Task", "Condition"]).size().to_string())
        language = frame[frame["Condition"].eq("Language robustness")]
        print("\nLanguage subtypes:")
        print(language.groupby(["Task", "Comparison / Subtype"]).size().to_string())
        cross = frame[frame["Condition"].astype(str).str.contains("Cross-task|Novel-object|counterfactual", case=False, regex=True)]
        print("\nCross-task / novel-object conditions:")
        print(cross.groupby(["Task", "Condition", "Comparison / Subtype"]).size().to_string())

    pi = pd.read_excel(SOURCE, sheet_name="Pi0.5")
    print("\n### Pi0.5 Referential Description episode 47")
    print(pi[(pi["Task"] == "Referential Disambiguation") & (pi["Episode"] == 47)][
        ["Status", "Task", "Episode", "Condition", "Comparison / Subtype", "Reference Episode", "Scene Family", "Prompt"]
    ].to_string(index=False))
    print("\n### Pi0.5 Referential Description episodes 40-49")
    print(pi[(pi["Task"] == "Referential Disambiguation") & pi["Episode"].between(40, 49)][
        ["Status", "Episode", "Condition", "Comparison / Subtype", "Reference Episode", "Scene Family", "Prompt"]
    ].to_string(index=False))
    molmo = pd.read_excel(SOURCE, sheet_name="MolmoAct2")
    print("\n### MolmoAct2 Relative Size episode 17")
    print(molmo[(molmo["Task"] == "Size Recognition") & (molmo["Episode"] == 17)][
        ["Status", "Task", "Episode", "Condition", "Comparison / Subtype", "Reference Episode", "Prompt"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
