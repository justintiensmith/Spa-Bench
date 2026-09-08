from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


INPUT = Path("failure_annotations_raw.csv")
OUTPUT = Path("failure_annotations_classified.csv")

TASK_NAMES = {
    "State Recognition": "Physical State",
    "Size Recognition": "Relative Size",
    "Referential Disambiguation": "Referential Description",
    "Ordinal Reference Ordering": "Ordinal Position",
    "Ordering/Sequencing": "Ordinal Position",
    "Relational Placement": "Relational Placement",
    "Counting": "Counting",
}

TARGET_SELECTION_TASKS = {
    "Physical State",
    "Relative Size",
    "Referential Description",
    "Ordinal Position",
}

OBJECT_ALIASES = {
    "airplane toy with propellers": ["airplane toy with propellers", "propellor plane", "propeller plane", "plane with propellers"],
    "airplane toy without propellers": ["airplane toy without propellers", "airplane toy without propellors", "non-propellor plane", "non-propeller plane", "plane without propellers"],
    "blue tape ball": ["blue tape ball", "tape ball"],
    "green highlighter": ["green highlighter", "highlighter"],
    "yellow pen": ["yellow pen"],
    "green pen": ["green pen"],
    "pink marker": ["pink marker", "pink pen"],
    "red block": ["red block"],
    "blue block": ["blue block"],
    "green block": ["green block"],
    "juggling ball": ["juggling ball"],
    "crushed pepsi can": ["crushed pepsi can", "pepsi can"],
    "crushed coke can": ["crushed coke can", "coke can"],
    "red pencil sharpener": ["red pencil sharpener", "red sharpener"],
    "green pencil sharpener": ["green pencil sharpener", "green sharpener"],
}


def has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def detect_named_objects(text: str) -> set[str]:
    found = set()
    for canonical, aliases in OBJECT_ALIASES.items():
        if any(alias in text for alias in aliases):
            found.add(canonical)
    return found


def target_match(row: pd.Series, task: str, text: str) -> bool | None:
    """Return whether the selected/attempted target matches the expected target."""
    expected = str(row.get("Expected Target / Action", "")).casefold()
    if task in {"Relative Size", "Ordinal Position", "Referential Description"}:
        expected_objects = detect_named_objects(expected)
        observed_objects = detect_named_objects(text)
        if expected_objects and observed_objects:
            return bool(expected_objects & observed_objects)
        return None
    if task == "Physical State":
        prompt = str(row.get("Prompt", "")).casefold()
        opposite_pairs = [
            ("upside-down", "upright"),
            ("upside down", "upright"),
            ("upright", "upside down"),
            ("upright", "upside-down"),
            ("open", "closed"),
            ("closed", "open"),
        ]
        for requested, contrary in opposite_pairs:
            if requested in prompt and contrary in text:
                return False
        requested_terms = [term for term in ["upside-down", "upside down", "upright", "open", "closed"] if term in prompt]
        if any(term in text for term in requested_terms):
            return True
    return None


def classify(row: pd.Series) -> pd.Series:
    task = TASK_NAMES.get(str(row["Task"]), str(row["Task"]))
    raw = "" if pd.isna(row["Observations"]) else str(row["Observations"]).strip()
    text = re.sub(r"\s+", " ", raw.casefold())

    if not text:
        return pd.Series(
            {
                "Canonical Task": task,
                "Primary Failure Mode": "Unannotated or unclear",
                "Secondary Flags": "",
                "Classification Confidence": "Low",
                "Classification Basis": "No qualitative annotation",
                "Needs Manual Review": "Yes",
            }
        )

    explicit_reasoning_success = has(
        r"reasoning (?:success|succeeded|successful|was good)|"
        r"successful reasoning|succeeded reasoning|correct (?:object|target|toy)|"
        r"went for correct|picked correctly|clearly went for",
        text,
    )
    explicit_reasoning_failure = has(
        r"reasoning failure|failed reasoning|failed at reasoning|"
        r"failed readoning|failed readoning|wrong (?:object|target|one)",
        text,
    )
    no_action = has(
        r"^(?:robot )?(?:didn['’]?t|did not) move[.!]?$|"
        r"no movement|kind of froze|just jittered around (?:the )?home|"
        r"moved around the home position|jittered around home|"
        r"didn['’]?t even move|did not even move|"
        r"slowly rotated.*didn['’]?t do anything|"
        r"moved wrist.*didn['’]?t move to",
        text,
    )
    timeout = has(
        r"tim(?:ed|ing) out|time ran out|ran out of time|"
        r"seconds (?:elapsed|was up)|episode time|"
        r"didn['’]?t have (?:enough )?time|did not have (?:enough )?time|"
        r"not enough time|the .* seconds was up",
        text,
    )
    failed_release = has(
        r"wouldn['’]?t (?:let go|release)|didn['’]?t (?:let go|release)|"
        r"couldn['’]?t (?:let go|release)|without letting it go|"
        r"never (?:let it go|released)",
        text,
    )
    premature_release = has(
        r"\bdropp(?:ed|ing)\b|\bfell\b|\bflew\b|\brolled out\b|"
        r"\blet go\b|\breleased? (?:it )?(?:early|too early)",
        text,
    ) and not failed_release
    grasp_failure = has(
        r"fail(?:ed|ure)? (?:at )?(?:to )?(?:grasp|grab|pick)|"
        r"grasp(?:ing)? fail|couldn['’]?t (?:grasp|grab|pick|get|take|remove)|"
        r"could not (?:grasp|grab|pick|get|take|remove)|"
        r"didn['’]?t (?:grasp|grab|pick|open (?:the )?gripper|take anything|remove anything)|"
        r"did not (?:grasp|grab|pick|open (?:the )?gripper|take anything|remove anything)|"
        r"never (?:grasped|grabbed|picked|moved it)|"
        r"grasp(?:ed|ing) (?:thin air|nothing)|grabbing (?:thin air|nothing)|"
        r"misgrip|bad grip|overgrip|over-grip|wrong gripping strategy|"
        r"knocked .* out of (?:range|frame|workspace)|"
        r"knocked it (?:over|around).*couldn['’]?t recover",
        text,
    )
    completed_manipulation = has(
        r"\b(?:picked|picked up|grabbed|placed|put|took|removed|moved it|rotated)\b",
        text,
    )
    relation_outcome = task == "Relational Placement" and has(
        r"\b(?:placed|put|moved|rotated|ended up)\b.*"
        r"\b(?:left|right|front|behind|back|bottom|top|near|beside)\b|"
        r"^placed (?:to |on |in )?(?:the )?(?:left|right|front|behind|back|bottom|top)",
        text,
    )
    count_outcome = task == "Counting" and completed_manipulation and not (
        grasp_failure or premature_release or timeout
    )
    selection_signal = completed_manipulation or has(r"\b(?:went for|went to|moved toward|moved towards|started going for|tried to pick|tried picking)\b", text)
    selected_target_matches = target_match(row, task, text)
    incomplete_home = has(r"didn['’]?t return (?:to )?home|did not return (?:to )?home", text)

    flags = []
    if no_action:
        flags.append("no action")
    if explicit_reasoning_failure:
        flags.append("reasoning/selection error")
    if grasp_failure:
        flags.append("grasp attempt failed")
    if relation_outcome or count_outcome:
        flags.append("incorrect spatial outcome")
    if premature_release:
        flags.append("premature release/drop")
    if failed_release:
        flags.append("failed to release")
    if timeout:
        flags.append("timeout")

    if no_action:
        primary, confidence, basis = "No action", "High", "Annotation explicitly reports no meaningful motion"
    elif explicit_reasoning_failure:
        primary = "Wrong target" if task in TARGET_SELECTION_TASKS else "Incorrect spatial outcome"
        confidence, basis = "High", "Annotation explicitly reports a reasoning error"
    elif explicit_reasoning_success and premature_release:
        primary, confidence, basis = "Premature release or dropped object", "High", "Correct choice stated; object was dropped or released"
    elif explicit_reasoning_success and grasp_failure:
        primary, confidence, basis = "Grasp failure", "High", "Correct choice stated; grasp failure reported"
    elif explicit_reasoning_success and timeout:
        primary, confidence, basis = "Timeout or incomplete execution", "High", "Correct choice stated; timeout reported"
    elif explicit_reasoning_success and (failed_release or incomplete_home):
        primary, confidence, basis = "Other execution failure", "High", "Correct spatial choice stated; completion criterion was not met"
    elif task in TARGET_SELECTION_TASKS and selected_target_matches is False:
        primary, confidence, basis = "Wrong target", "High", "Observed target differs from the expected target"
    elif relation_outcome:
        primary, confidence, basis = "Incorrect spatial outcome", "High", "Placement relation reported on a failed relational trial"
    elif count_outcome:
        primary, confidence, basis = "Incorrect spatial outcome", "Medium", "Completed manipulation did not achieve the requested count"
    elif premature_release:
        primary, confidence, basis = "Premature release or dropped object", "High", "Annotation reports a drop or early release"
    elif grasp_failure:
        primary, confidence, basis = "Grasp failure", "High", "Annotation reports an unsuccessful grasp attempt"
    elif timeout:
        primary, confidence, basis = "Timeout or incomplete execution", "High", "Annotation explicitly reports insufficient time"
    elif task in TARGET_SELECTION_TASKS and completed_manipulation:
        primary, confidence, basis = (
            "Wrong target",
            "Medium",
            "A completed pick/place is reported on a failed target-selection trial",
        )
    elif task in TARGET_SELECTION_TASKS and selection_signal and grasp_failure:
        primary, confidence, basis = "Grasp failure", "Medium", "A target was approached but the grasp did not complete"
    elif failed_release:
        primary, confidence, basis = "Other execution failure", "High", "Object was not released at the goal"
    elif has(r"knock|drift|jitter|hesitat|pushed|couldn['’]?t recover|went home|returned home", text):
        primary, confidence, basis = "Other execution failure", "Medium", "Annotation reports an execution or recovery failure"
    else:
        primary, confidence, basis = "Unannotated or unclear", "Low", "Annotation does not uniquely identify a failure mode"

    return pd.Series(
        {
            "Canonical Task": task,
            "Primary Failure Mode": primary,
            "Secondary Flags": "; ".join(flags),
            "Classification Confidence": confidence,
            "Classification Basis": basis,
            "Needs Manual Review": "Yes" if confidence == "Low" else "No",
        }
    )


MANUAL_OVERRIDES = {
    ("GR00T Frozen LLM", "Ordinal Position", 109): ("Wrong target", "High", "Approached green highlighter; expected yellow pen"),
    ("GR00T Frozen LLM", "Relational Placement", 60): ("Grasp failure", "High", "Correct red block was approached but not picked"),
    ("GR00T Frozen LLM", "Relational Placement", 64): ("Other execution failure", "High", "Correct choice stated; task completion failed"),
    ("GR00T Frozen LLM", "Referential Description", 66): ("Wrong target", "High", "Diverted from expected Coke can to Pepsi can"),
    ("GR00T Frozen LLM", "Referential Description", 74): ("Wrong target", "High", "Selected red sharpener; expected green sharpener"),
    ("GR00T Frozen LLM", "Relative Size", 60): ("Other execution failure", "Medium", "Target was disturbed before recovery switched to a non-target"),
    ("MolmoAct2", "Relational Placement", 40): ("Incorrect spatial outcome", "High", "Final placement was predominantly below rather than left"),
    ("MolmoAct2", "Relative Size", 78): ("Wrong target", "High", "Approached Pepsi can; expected juggling ball"),
    ("MolmoAct2", "Relative Size", 83): ("Wrong target", "High", "Approached Pepsi can; expected juggling ball"),
    ("MolmoAct2", "Relative Size", 102): ("Wrong target", "High", "Selected red sharpener; expected green block"),
    ("Pi0.5", "Physical State", 20): ("Wrong target", "High", "Selected upright cup; requested upside-down cup"),
    ("Pi0.5", "Physical State", 91): ("Wrong target", "High", "Selected upside-down container; requested upright container"),
    ("Pi0.5", "Physical State", 92): ("Wrong target", "High", "Selected upright cup; requested upside-down cup"),
    ("Pi0.5", "Ordinal Position", 35): ("Wrong target", "High", "Approached non-target objects; expected blue tape ball"),
    ("Pi0.5", "Ordinal Position", 83): ("Wrong target", "High", "Selected airplane toy; expected blue tape ball"),
    ("Pi0.5", "Relative Size", 76): ("Wrong target", "High", "Selected red sharpener; expected green block"),
    ("Pi0.5", "Relative Size", 90): ("Wrong target", "High", "Selected red sharpener; expected green block"),
    ("Pi0.5", "Relative Size", 91): ("Grasp failure", "High", "Attempted an empty-space grasp"),
    ("Pi0.5", "Relative Size", 92): ("Wrong target", "High", "Selected red sharpener; expected green block"),
    ("Pi0.5", "Relative Size", 93): ("Wrong target", "High", "Approached soda can; expected juggling ball"),
}


data = pd.read_csv(INPUT)
classified = data.apply(classify, axis=1)
out = pd.concat([data, classified], axis=1)
for idx, row in out.iterrows():
    key = (row["Model"], row["Canonical Task"], int(row["Episode"]))
    if key not in MANUAL_OVERRIDES:
        continue
    mode, confidence, basis = MANUAL_OVERRIDES[key]
    out.at[idx, "Primary Failure Mode"] = mode
    out.at[idx, "Classification Confidence"] = confidence
    out.at[idx, "Classification Basis"] = basis
    out.at[idx, "Needs Manual Review"] = "No"
out.to_csv(OUTPUT, index=False)

primary = out[
    (out["Model"].isin(["GR00T Frozen LLM", "MolmoAct2", "Pi0.5"]))
    & (out["Condition"] == "Concept/compositional transfer")
]

print(f"wrote {len(out)} classified failures to {OUTPUT}")
print(f"primary novel failures: {len(primary)}")
print("\nPrimary failure modes by model")
print(pd.crosstab(primary["Model"], primary["Primary Failure Mode"]).to_string())
print("\nPrimary failure modes by task")
print(pd.crosstab(primary["Canonical Task"], primary["Primary Failure Mode"]).to_string())
print("\nConfidence")
print(primary["Classification Confidence"].value_counts().to_string())
print("\nLow-confidence primary annotations")
for _, row in primary[primary["Classification Confidence"] == "Low"].iterrows():
    print(
        f"{row['Model']} | {row['Canonical Task']} | ep {row['Episode']} | "
        f"{str(row['Observations'])[:300]}"
    )
