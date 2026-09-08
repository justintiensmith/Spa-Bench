from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prepare_all_failure_audit import (
    COMPLETE_MODELS,
    MODE_ORDER,
    OUTPUT_CSV,
    PAYLOAD,
    ROOT,
    TASK_ORDER,
    merged_flags,
    row_key,
)


WORKBOOK = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "Spa_Bench_All_Failure_Audit.xlsx"
)
REVIEW_ARCHIVE = ROOT / "completed_review_queue.csv"

SUCCESS_KEYS = {
    ("MolmoAct2", "Relative Size", 17, "In-distribution concept baseline"),
    ("Pi0.5", "Referential Description", 47, "Language robustness"),
}

MODE_ALIASES = {
    "Grasping": "Grasp failure",
}

SECONDARY_ADDITIONS = {
    ("VLA-0", "Counting", 2, "In-distribution concept baseline"): ["grasp attempt failed"],
    ("GR00T Frozen LLM", "Relational Placement", 46, "Language robustness"): ["incorrect spatial outcome"],
    ("GR00T Frozen LLM", "Relational Placement", 143, "Violated-relation correction control"): ["wrong target", "incorrect spatial outcome"],
    ("GR00T Full Fine-Tune", "Counting", 5, "In-distribution concept baseline"): ["grasp attempt failed"],
    ("MolmoAct2", "Referential Description", 149, "No valid candidate category / no movement"): ["wrong-object selection", "grasp attempt failed", "unintended object displacement"],
    ("Pi0.5", "Physical State", 5, "In-distribution concept baseline"): ["correct target initially approached", "control drift/instability"],
    ("Pi0.5", "Physical State", 13, "In-distribution concept baseline"): ["target displaced out of reach", "wrong target during recovery"],
    ("Pi0.5", "Physical State", 144, "No valid target / no movement"): ["object selected despite no-movement instruction"],
    ("Pi0.5", "Referential Description", 26, "Language robustness"): ["target displaced"],
}


def clean_review_secondary(value: object) -> object:
    if pd.isna(value) or not str(value).strip():
        return None
    text = str(value).strip()
    # This value was introduced by a shifted paste and is not a failure flag.
    if text == "Relative Size":
        return None
    return text


def main() -> None:
    all_failures = pd.read_excel(WORKBOOK, sheet_name="All Classified Failures", header=2)
    review = pd.read_excel(WORKBOOK, sheet_name="Review Queue", header=2)
    review.to_csv(REVIEW_ARCHIVE, index=False)

    if len(all_failures) != 1367 or len(review) != 28:
        raise ValueError(
            f"Unexpected source sizes: {len(all_failures)} all failures and {len(review)} review rows"
        )

    positions = {row_key(row): idx for idx, row in all_failures.iterrows()}
    review_keys = {row_key(row) for _, row in review.iterrows()}
    if not SUCCESS_KEYS.issubset(review_keys):
        raise ValueError(f"Success corrections are missing from the review queue: {SUCCESS_KEYS - review_keys}")

    for _, reviewed in review.iterrows():
        key = row_key(reviewed)
        if key in SUCCESS_KEYS:
            continue
        idx = positions[key]
        observation = reviewed.get("Current Observation")
        if pd.notna(observation) and str(observation).strip():
            all_failures.at[idx, "Observation"] = str(observation).strip()

        mode = str(reviewed.get("Suggested Primary Mode", "")).strip()
        mode = MODE_ALIASES.get(mode, mode)
        if mode not in MODE_ORDER or mode == "Unannotated or unclear":
            raise ValueError(f"Reviewed row {key} does not have a resolved canonical mode: {mode!r}")

        current_flags = clean_review_secondary(reviewed.get("Current Secondary Flags"))
        all_failures.at[idx, "Primary Failure Mode"] = mode
        all_failures.at[idx, "Secondary Flags"] = merged_flags(
            mode, current_flags, SECONDARY_ADDITIONS.get(key, [])
        )
        all_failures.at[idx, "Classification Confidence"] = "High"
        all_failures.at[idx, "Classification Basis"] = "User-confirmed during follow-up rollout review."
        all_failures.at[idx, "Needs Manual Review"] = "No"

    keep = ~all_failures.apply(row_key, axis=1).isin(SUCCESS_KEYS)
    all_failures = all_failures.loc[keep].reset_index(drop=True)
    all_failures["Canonical Task"] = all_failures["Task"]

    if all_failures["Needs Manual Review"].eq("Yes").any():
        unresolved = all_failures[all_failures["Needs Manual Review"].eq("Yes")]
        raise ValueError(f"Unresolved rows remain after user review: {len(unresolved)}")
    if all_failures["Primary Failure Mode"].eq("Unannotated or unclear").any():
        unresolved = all_failures[all_failures["Primary Failure Mode"].eq("Unannotated or unclear")]
        raise ValueError(f"Unannotated rows remain after user review: {len(unresolved)}")

    all_failures.to_csv(OUTPUT_CSV, index=False)

    primary = all_failures[
        all_failures["Model"].isin(COMPLETE_MODELS)
        & all_failures["Condition"].eq("Concept/compositional transfer")
    ].copy()
    primary["Model"] = pd.Categorical(primary["Model"], COMPLETE_MODELS, ordered=True)
    primary["Canonical Task"] = pd.Categorical(primary["Canonical Task"], TASK_ORDER, ordered=True)
    primary["Primary Failure Mode"] = pd.Categorical(primary["Primary Failure Mode"], MODE_ORDER, ordered=True)
    primary = primary.sort_values(["Model", "Canonical Task", "Episode"])
    primary_records = primary.copy()
    for column in ["Model", "Canonical Task", "Primary Failure Mode"]:
        primary_records[column] = primary_records[column].astype(str)

    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    payload["source_evaluations"] = "Spa_Bench_All_Failure_Audit.xlsx with completed user review"
    payload["primary_failures"] = json.loads(primary_records.to_json(orient="records"))
    payload["all_failures"] = json.loads(all_failures.to_json(orient="records"))
    payload["review_queue"] = []
    payload["condition_order"] = sorted(all_failures["Condition"].dropna().astype(str).unique())
    payload["scope"].update({
        "total_failures": int(len(primary)),
        "all_failures": int(len(all_failures)),
        "review_queue": 0,
        "missing_observations": 0,
        "ambiguous_nonblank": 0,
        "residual_unclear": 0,
        "unnecessary_interventions": int(all_failures["Primary Failure Mode"].eq("Unnecessary intervention").sum()),
    })
    PAYLOAD.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved completed review archive: {REVIEW_ARCHIVE}")
    print(f"Updated data source: {OUTPUT_CSV}")
    print(f"Updated payload: {PAYLOAD}")
    print(f"All failures: {len(all_failures)}")
    print(f"Primary novel failures: {len(primary)}")
    print("\nAll-failure primary modes:")
    print(all_failures["Primary Failure Mode"].value_counts().reindex(MODE_ORDER, fill_value=0).to_string())


if __name__ == "__main__":
    main()
