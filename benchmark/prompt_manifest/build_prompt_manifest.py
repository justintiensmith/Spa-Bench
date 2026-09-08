#!/usr/bin/env python3
"""Build and validate the Spa-Bench episode-level prompt manifest.

The six Hugging Face repositories are treated as immutable inputs. This script
reads their metadata from a local Hugging Face cache and reconstructs the
recording annotations from the benchmark PDF. It writes only to ``--output-dir``.

Optional runtime dependencies:
  - pypdf, for reading the benchmark PDF
  - pyarrow, for reading cached Hugging Face parquet metadata
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_VERSION = "v1"


@dataclass(frozen=True)
class SourceDataset:
    repo_name: str
    task_family: str
    revision: str

    @property
    def repo_id(self) -> str:
        return f"justintiensmith/{self.repo_name}"


SOURCES = (
    SourceDataset(
        "MT_State_Recognition_200",
        "state_recognition",
        "168e12e735da9ad62716dca89cff660b53082cc3",
    ),
    SourceDataset(
        "SP_Relational_Placement_200",
        "relational_placement",
        "8eff46af18af7a9a6f763ed975f8b3357c673685",
    ),
    SourceDataset(
        "SP_Referential_Disambiguation_200",
        "referential_disambiguation",
        "2642784f74a0c91bc118702b7993895aacd311f5",
    ),
    SourceDataset(
        "SP_Sequencing_200",
        "ordering",
        "1cda4c4c3c6ae1fa4b5dc6d2cf4c887bb9f1da4e",
    ),
    SourceDataset(
        "SP_Counting_200",
        "counting",
        "6591c0f19952e23010b7c6a0630e4d60f8714cbb",
    ),
    SourceDataset(
        "MT_Size_Recognition_200",
        "size_recognition",
        "3a6e75d91e8339a87eebd8e545d87b148ae19925",
    ),
)

SOURCE_BY_FAMILY = {source.task_family: source for source in SOURCES}

VERIFIED_OBJECT_INVENTORY = {
    "relational_placement": {
        "red_block": "red block",
        "blue_block": "blue block",
        "green_pen": "green pen",
        "pink_marker": "pink marker",
    },
    "referential_disambiguation": {
        "crushed_coke_can": "crushed Coke can",
        "crushed_pepsi_can": "crushed Pepsi can",
        "green_pencil_sharpener": "green pencil sharpener",
        "red_pencil_sharpener": "red pencil sharpener",
        "green_pen": "green pen",
        "yellow_pen": "yellow pen",
        "airplane_without_propellers": "airplane toy without propellers",
        "airplane_with_propellers": "airplane toy with propellers",
    },
    "state_recognition": {
        "white_cup_a": "white cup A",
        "white_cup_b": "white cup B",
        "yellow_white_striped_cup_a": "yellow-white striped cup A",
        "yellow_white_striped_cup_b": "yellow-white striped cup B",
        "glass_spice_container_a": "glass spice container A",
        "glass_spice_container_b": "glass spice container B",
        "brown_cup_a": "brown cup A",
        "brown_cup_b": "brown cup B",
    },
    "ordering": {
        "airplane_with_propellers": "airplane toy with propellers",
        "blue_tape_ball": "blue tape ball",
        "green_highlighter": "green highlighter",
        "yellow_pen": "yellow pen",
    },
    "counting": {
        "green_pencil_sharpener": "green pencil sharpener",
        "airplane_without_propellers": "airplane toy without propellers",
        "blue_pen": "blue pen",
        "yellow_block": "yellow block",
    },
    "size_recognition": {
        "green_block": "green block",
        "crushed_pepsi_can": "crushed Pepsi can",
        "juggling_ball": "juggling ball",
        "red_pencil_sharpener": "red pencil sharpener",
    },
}

MANIFEST_COLUMNS = (
    "manifest_version",
    "global_episode_id",
    "source_repo_id",
    "source_revision",
    "source_episode_index",
    "source_task",
    "source_episode_length",
    "task_family",
    "pdf_page",
    "start_type",
    "target_id",
    "target_name",
    "target_category",
    "reference_ids_json",
    "scene_objects_json",
    "scene_attributes_json",
    "scene_size",
    "difficulty",
    "initial_count",
    "final_count",
    "action_direction",
    "target_slot_left",
    "target_slot_right",
    "state",
    "orientation",
    "demonstrated_concept",
    "assigned_concept",
    "semantic_cell",
    "holdout_reason",
    "prompt_type",
    "template_id",
    "assigned_prompt",
    "fold_10",
    "recommended_split",
    "annotation_flags_json",
)


def normalize_text(value: str) -> str:
    replacements = {
        "\u00a0": " ",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def slug(value: str) -> str:
    value = normalize_text(value).lower()
    value = value.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def stable_digest(*parts: object) -> str:
    joined = "||".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class PageRange:
    """Normalized text from a set of PDF pages with start-page lookup."""

    def __init__(self, reader: Any, page_numbers: Iterable[int]) -> None:
        self._offsets: list[int] = []
        self._pages: list[int] = []
        parts: list[str] = []
        offset = 0
        for page_number in page_numbers:
            text = normalize_text(reader.pages[page_number - 1].extract_text() or "")
            self._offsets.append(offset)
            self._pages.append(page_number)
            parts.append(text)
            offset += len(text) + 1
        self.text = " ".join(parts)

    def page_at(self, position: int) -> int:
        index = bisect.bisect_right(self._offsets, position) - 1
        return self._pages[max(index, 0)]


def base_record(
    family: str,
    episode_index: int,
    pdf_page: int,
    start_type: str,
    target_id: str,
    target_name: str,
    target_category: str,
) -> dict[str, Any]:
    source = SOURCE_BY_FAMILY[family]
    return {
        "manifest_version": MANIFEST_VERSION,
        "global_episode_id": f"{source.repo_id}:{episode_index:03d}",
        "source_repo_id": source.repo_id,
        "source_revision": source.revision,
        "source_episode_index": episode_index,
        "source_task": "",
        "source_episode_length": "",
        "task_family": family,
        "pdf_page": pdf_page,
        "start_type": start_type,
        "target_id": target_id,
        "target_name": target_name,
        "target_category": target_category,
        "reference_ids_json": "[]",
        "scene_objects_json": "[]",
        "scene_attributes_json": "[]",
        "scene_size": "",
        "difficulty": "",
        "initial_count": "",
        "final_count": "",
        "action_direction": "",
        "target_slot_left": "",
        "target_slot_right": "",
        "state": "",
        "orientation": "",
        "demonstrated_concept": "",
        "assigned_concept": "",
        "semantic_cell": "seen",
        "holdout_reason": "",
        "prompt_type": "semantic_reasoning",
        "template_id": "",
        "assigned_prompt": "",
        "fold_10": episode_index % 10,
        "recommended_split": "train",
        "annotation_flags_json": "[]",
    }


SIZE_OBJECTS = {
    "Sharpener": ("red_pencil_sharpener", "red pencil sharpener", 1),
    "Block": ("green_block", "green block", 2),
    "Ball": ("juggling_ball", "juggling ball", 3),
    "Can": ("crushed_pepsi_can", "crushed Pepsi can", 4),
}


def parse_size(reader: Any) -> list[dict[str, Any]]:
    pages = PageRange(reader, range(6, 11))
    pattern = re.compile(r"Episode\s+(\d+):\s+(Home|Recovery)\s+Start\.\s+([^.]*)\.")
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(pages.text):
        episode = int(match.group(1))
        start_type = "home" if match.group(2) == "Home" else "recovery"
        scene_labels = [item.strip() for item in match.group(3).split(",") if item.strip()]
        scene = [SIZE_OBJECTS[item][0] for item in scene_labels]
        if episode < 50:
            target_key = "Sharpener"
        elif episode < 100:
            target_key = "Block"
        elif episode < 150:
            target_key = "Ball"
        else:
            target_key = "Can"
        target_id, target_name, target_rank = SIZE_OBJECTS[target_key]
        ranks = [SIZE_OBJECTS[item][2] for item in scene_labels]
        if target_rank == min(ranks):
            concept = "smallest"
        elif target_rank == max(ranks):
            concept = "largest"
        else:
            raise ValueError(f"Size episode {episode} target is not an extreme")
        held_out = (target_id, concept) in {
            ("green_block", "largest"),
            ("juggling_ball", "smallest"),
        }
        row = base_record(
            "size_recognition",
            episode,
            pages.page_at(match.start()),
            start_type,
            target_id,
            target_name,
            "object",
        )
        row.update(
            {
                "scene_objects_json": json.dumps(scene),
                "scene_size": len(scene),
                "demonstrated_concept": concept,
                "assigned_concept": "object_identity" if held_out else concept,
                "semantic_cell": "held_out" if held_out else "seen",
                "holdout_reason": (f"withhold object-rank pairing {target_id}+{concept}" if held_out else ""),
                "prompt_type": "identity" if held_out else "semantic_reasoning",
            }
        )
        rows.append(row)
    return rows


STATE_ITEM_PATTERN = re.compile(
    r"(White Cup [AB]|Yellow Cup [AB]|Brown Cup [AB]|"
    r"Glass Spice Container [AB])\s+\((Open|Closed),\s+(RSU|UD)\)"
)


def state_item(raw_name: str, state: str, orientation: str) -> dict[str, str]:
    instance = raw_name[-1]
    family_raw = raw_name[:-2]
    family_names = {
        "White Cup": ("white_cup", "white cup"),
        "Yellow Cup": ("yellow_white_striped_cup", "yellow-white striped cup"),
        "Brown Cup": ("brown_cup", "brown cup"),
        "Glass Spice Container": ("glass_spice_container", "glass spice container"),
    }
    family_id, family_name = family_names[family_raw]
    return {
        "object_id": f"{family_id}_{instance.lower()}",
        "name": f"{family_name} {instance}",
        "category_id": family_id,
        "category_name": family_name,
        "instance": instance,
        "state": state.lower(),
        "orientation": "right_side_up" if orientation == "RSU" else "upside_down",
    }


def parse_state(reader: Any) -> list[dict[str, Any]]:
    pages = PageRange(reader, range(11, 23))
    pattern = re.compile(
        r"Episode\s+(\d+)\s+-\s+(Home|Recovery)\s+Start:\s+(.*?)"
        r"(?=\s+Episode\s+\d+\s+-\s+(?:Home|Recovery)\s+Start:|$)"
    )
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(pages.text):
        episode = int(match.group(1))
        start_type = "home" if match.group(2) == "Home" else "recovery"
        items = [
            state_item(raw_name, state, orientation)
            for raw_name, state, orientation in STATE_ITEM_PATTERN.findall(match.group(3))
        ]
        if not items:
            raise ValueError(f"No state items parsed for episode {episode}")
        target = items[0]
        held_out = target["state"] == "closed" and target["orientation"] == "upside_down"
        row = base_record(
            "state_recognition",
            episode,
            pages.page_at(match.start()),
            start_type,
            target["object_id"],
            target["name"],
            target["category_name"],
        )
        flags: list[str] = []
        if held_out:
            same_category = [item for item in items if item["category_id"] == target["category_id"]]
            unique_state = sum(item["state"] == target["state"] for item in same_category) == 1
            unique_orientation = (
                sum(item["orientation"] == target["orientation"] for item in same_category) == 1
            )
            candidates: list[str] = []
            if unique_state:
                candidates.append("closed")
            if unique_orientation:
                candidates.append("upside_down")
            if candidates:
                assigned_concept = candidates[
                    int(stable_digest(row["global_episode_id"], "state_partial"), 16) % len(candidates)
                ]
                prompt_type = "semantic_partial"
            else:
                assigned_concept = "object_instance"
                prompt_type = "identity"
                flags.append("state_partial_prompt_not_unique")
        else:
            assigned_concept = f"{target['state']}_{target['orientation']}"
            prompt_type = "semantic_reasoning"
            same_description = [
                item
                for item in items
                if item["category_id"] == target["category_id"]
                and item["state"] == target["state"]
                and item["orientation"] == target["orientation"]
            ]
            if len(same_description) != 1:
                flags.append("state_full_prompt_not_unique")
        row.update(
            {
                "scene_objects_json": json.dumps([item["object_id"] for item in items]),
                "scene_attributes_json": json.dumps(items, sort_keys=True),
                "scene_size": len(items),
                "state": target["state"],
                "orientation": target["orientation"],
                "demonstrated_concept": (f"{target['state']}_{target['orientation']}"),
                "assigned_concept": assigned_concept,
                "semantic_cell": "held_out" if held_out else "seen",
                "holdout_reason": ("withhold closed+upside-down state conjunction" if held_out else ""),
                "prompt_type": prompt_type,
                "annotation_flags_json": json.dumps(flags),
            }
        )
        rows.append(row)
    return rows


RELATION_OBJECTS = {
    "green pen": ("green_pen", "green pen"),
    "red block": ("red_block", "red block"),
    "pink marker": ("pink_marker", "pink marker"),
    "blue block": ("blue_block", "blue block"),
}


def canonical_relation_object(raw_name: str) -> tuple[str, str]:
    name = normalize_text(raw_name).lower().strip(" .,")
    if name not in RELATION_OBJECTS:
        raise ValueError(f"Unknown relational object: {raw_name!r}")
    return RELATION_OBJECTS[name]


def trim_entry_tail(value: str) -> str:
    return re.split(
        r"\s+(?:[A-D]\.\s+(?:FRONT|BACK|NEXT|LEFT|RIGHT|CLOSEST|FURTHEST|BETWEEN)|"
        r"={3,}|-{3,}|PART\s+\d+:|TARGET\s+\d+:|Slot\s+\d+:|PROMPT:)",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()


def parse_relational(reader: Any) -> list[dict[str, Any]]:
    pages = PageRange(reader, range(24, 30))
    entry = re.compile(r"\[(\d{3})\]\s+(Home|Rec)\s+\|\s+Ref:\s+(.+?)\s+\|\s+Scene:\s+")
    matches = list(entry.finditer(pages.text))
    rows: list[dict[str, Any]] = []
    all_scene_ids = [item[0] for item in RELATION_OBJECTS.values()]
    targets = (
        ("green_pen", "green pen"),
        ("red_block", "red block"),
        ("pink_marker", "pink marker"),
        ("blue_block", "blue block"),
    )
    for index, match in enumerate(matches):
        episode = int(match.group(1))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(pages.text)
        scene_raw = trim_entry_tail(pages.text[match.end() : end])
        target_id, target_name = targets[episode // 50]
        local = episode % 50
        if local < 12:
            demonstrated = assigned = "front"
        elif local < 25:
            demonstrated = assigned = "behind"
        elif local < 37:
            demonstrated, assigned = "left", "next_to"
        else:
            demonstrated, assigned = "right", "next_to"
        held_out = demonstrated in {"left", "right"}
        reference_id, reference_name = canonical_relation_object(match.group(3))
        if scene_raw.lower().startswith("full table"):
            scene = all_scene_ids
        else:
            scene = [canonical_relation_object(item)[0] for item in scene_raw.split(",") if item.strip()]
        row = base_record(
            "relational_placement",
            episode,
            pages.page_at(match.start()),
            "home" if match.group(2) == "Home" else "recovery",
            target_id,
            target_name,
            "object",
        )
        row.update(
            {
                "reference_ids_json": json.dumps([reference_id]),
                "scene_objects_json": json.dumps(scene),
                "scene_size": len(scene),
                "demonstrated_concept": demonstrated,
                "assigned_concept": assigned,
                "semantic_cell": "held_out" if held_out else "seen",
                "holdout_reason": (
                    f"withhold directed horizontal relation {demonstrated}" if held_out else ""
                ),
                "prompt_type": ("semantic_generic" if held_out else "semantic_reasoning"),
                "_reference_names": [reference_name],
            }
        )
        rows.append(row)
    return rows


REFERENTIAL_OBJECTS = {
    "coke can": ("crushed_coke_can", "crushed Coke can"),
    "pepsi can": ("crushed_pepsi_can", "crushed Pepsi can"),
    "crushed coke can": ("crushed_coke_can", "crushed Coke can"),
    "crushed pepsi can": ("crushed_pepsi_can", "crushed Pepsi can"),
    "green sharpener": ("green_pencil_sharpener", "green pencil sharpener"),
    "green pencil sharpener": (
        "green_pencil_sharpener",
        "green pencil sharpener",
    ),
    "red sharpener": ("red_pencil_sharpener", "red pencil sharpener"),
    "red pencil sharpener": ("red_pencil_sharpener", "red pencil sharpener"),
    "green pen": ("green_pen", "green pen"),
    "yellow pen": ("yellow_pen", "yellow pen"),
    "propeller plane": (
        "airplane_with_propellers",
        "airplane toy with propellers",
    ),
    "airplane with propellers": (
        "airplane_with_propellers",
        "airplane toy with propellers",
    ),
    "airplane toy with propellers": (
        "airplane_with_propellers",
        "airplane toy with propellers",
    ),
    "non-propeller plane": (
        "airplane_without_propellers",
        "airplane toy without propellers",
    ),
    "airplane without propellers": (
        "airplane_without_propellers",
        "airplane toy without propellers",
    ),
    "airplane toy without propellers": (
        "airplane_without_propellers",
        "airplane toy without propellers",
    ),
}


def canonical_referential_object(raw_name: str) -> tuple[str, str]:
    name = normalize_text(raw_name).lower().strip(" .")
    if name not in REFERENTIAL_OBJECTS:
        raise ValueError(f"Unknown referential object: {raw_name!r}")
    return REFERENTIAL_OBJECTS[name]


def parse_reference_names(prompt: str, concept: str) -> list[str]:
    normalized = normalize_text(prompt).lower().rstrip(".")
    if concept == "closest":
        raw = normalized.split(" closest to the ", 1)[1]
        return [canonical_referential_object(raw)[1]]
    if concept == "furthest":
        raw = normalized.split(" furthest from the ", 1)[1]
        return [canonical_referential_object(raw)[1]]
    between = re.search(r" between the (.+?) and the (.+)$", normalized)
    if between is None:
        raise ValueError(f"Cannot parse between prompt: {prompt}")
    return [
        canonical_referential_object(between.group(1))[1],
        canonical_referential_object(between.group(2))[1],
    ]


def parse_referential(reader: Any) -> list[dict[str, Any]]:
    pages = PageRange(reader, range(30, 45))
    entry = re.compile(
        r"(?<!\d)(\d{3})\s+\[(Home|Recov)\]\s+\[Correct=([LR])\]\s+"
        r"\[([^\]]+)\]\s+\[([^\]]+)\]\s+\|\s+\"([^\"]+)\"\s+\|\s+"
        r"Target:\s+(.+?)\s+\|\s+Scene:\s+"
    )
    matches = list(entry.finditer(pages.text))
    categories = ("crushed soda can", "pencil sharpener", "pen", "airplane toy")
    rows: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        episode = int(match.group(1))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(pages.text)
        scene_raw = pages.text[match.end() : end].split("| Extra:", 1)[0]
        scene_raw = trim_entry_tail(scene_raw)
        prompt = normalize_text(match.group(6))
        prompt_lower = prompt.lower()
        if " closest " in f" {prompt_lower} ":
            concept = "closest"
        elif " furthest " in f" {prompt_lower} ":
            concept = "furthest"
        elif " between " in f" {prompt_lower} ":
            concept = "between"
        else:
            raise ValueError(f"Unknown referential concept: {prompt}")
        target_id, target_name = canonical_referential_object(match.group(7))
        scene = [canonical_referential_object(item)[0] for item in scene_raw.split(",") if item.strip()]
        reference_names = parse_reference_names(prompt, concept)
        reference_ids = [canonical_referential_object(name)[0] for name in reference_names]
        held_out = concept == "furthest"
        row = base_record(
            "referential_disambiguation",
            episode,
            pages.page_at(match.start()),
            "home" if match.group(2) == "Home" else "recovery",
            target_id,
            target_name,
            categories[episode // 50],
        )
        row.update(
            {
                "reference_ids_json": json.dumps(reference_ids),
                "scene_objects_json": json.dumps(scene),
                "scene_size": len(scene),
                "difficulty": f"{match.group(4)}|{match.group(5)}|correct_{match.group(3).lower()}",
                "demonstrated_concept": concept,
                "assigned_concept": "object_identity" if held_out else concept,
                "semantic_cell": "held_out" if held_out else "seen",
                "holdout_reason": "withhold furthest relation" if held_out else "",
                "prompt_type": "identity" if held_out else "semantic_reasoning",
                "_reference_names": reference_names,
            }
        )
        rows.append(row)
    return rows


ORDERING_OBJECTS = {
    "airplane toy": (
        "airplane_with_propellers",
        "airplane toy with propellers",
    ),
    "blue tape ball": ("blue_tape_ball", "blue tape ball"),
    "ball of blue tape": ("blue_tape_ball", "blue tape ball"),
    "green highlighter": ("green_highlighter", "green highlighter"),
    "yellow pen": ("yellow_pen", "yellow pen"),
}

ORDINALS = {1: "first", 2: "second", 3: "third", 4: "fourth"}
ORDERING_HOLDOUTS = {"first_from_right", "third_from_left"}


def canonical_ordering_object(raw_name: str) -> tuple[str, str]:
    name = normalize_text(raw_name).lower().strip(" .,")
    if name not in ORDERING_OBJECTS:
        raise ValueError(f"Unknown ordering object: {raw_name!r}")
    return ORDERING_OBJECTS[name]


def ordering_concept(prompt: str) -> str:
    normalized = normalize_text(prompt).lower()
    match = re.fullmatch(r"(first|second|third|fourth) from (left|right)", normalized)
    if match is None:
        raise ValueError(f"Unknown ordering prompt: {prompt!r}")
    return f"{match.group(1)}_from_{match.group(2)}"


def choose_ordering_assignment(rows: list[dict[str, Any]]) -> None:
    counts: Counter[tuple[str, str]] = Counter()
    for row in sorted(rows, key=lambda item: item["source_episode_index"]):
        left = int(row["target_slot_left"])
        right = int(row["target_slot_right"])
        candidates = [
            f"{ORDINALS[left]}_from_left",
            f"{ORDINALS[right]}_from_right",
        ]
        candidates = [candidate for candidate in candidates if candidate not in ORDERING_HOLDOUTS]
        demonstrated = row["demonstrated_concept"]
        if demonstrated in ORDERING_HOLDOUTS:
            candidates = [candidate for candidate in candidates if candidate != demonstrated]
        if not candidates:
            row["assigned_concept"] = "object_identity"
            row["prompt_type"] = "identity"
            continue
        target = row["target_id"]
        candidates.sort(
            key=lambda concept: (
                counts[(target, concept)],
                stable_digest(row["global_episode_id"], concept),
            )
        )
        assigned = candidates[0]
        counts[(target, assigned)] += 1
        row["assigned_concept"] = assigned
        row["prompt_type"] = (
            "semantic_equivalent" if demonstrated in ORDERING_HOLDOUTS else "semantic_reasoning"
        )


def parse_ordering(reader: Any) -> list[dict[str, Any]]:
    pages = PageRange(reader, range(45, 55))
    usable_text = pages.text.split("Data collected by accident", 1)[0]
    entry = re.compile(
        r"Episode\s+(\d+):\s+(Home|Recovery)\s+\|\s+Prompt:\s+\"([^\"]+)\""
        r"\s+\|\s+Scene:\s+"
    )
    matches = list(entry.finditer(usable_text))
    targets = (
        ("airplane_with_propellers", "airplane toy with propellers"),
        ("blue_tape_ball", "blue tape ball"),
        ("green_highlighter", "green highlighter"),
        ("yellow_pen", "yellow pen"),
    )
    rows: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        episode = int(match.group(1))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(usable_text)
        scene_raw = trim_entry_tail(usable_text[match.end() : end])
        scene_items = [item for item in scene_raw.split(",") if item.strip()]
        scene_pairs = [canonical_ordering_object(item) for item in scene_items]
        scene = [item[0] for item in scene_pairs]
        target_id, target_name = targets[episode // 50]
        left = scene.index(target_id) + 1
        right = len(scene) - left + 1
        demonstrated = ordering_concept(match.group(3))
        held_out = demonstrated in ORDERING_HOLDOUTS
        row = base_record(
            "ordering",
            episode,
            pages.page_at(match.start()),
            "home" if match.group(2) == "Home" else "recovery",
            target_id,
            target_name,
            "object",
        )
        row.update(
            {
                "scene_objects_json": json.dumps(scene),
                "scene_size": len(scene),
                "target_slot_left": left,
                "target_slot_right": right,
                "demonstrated_concept": demonstrated,
                "semantic_cell": "held_out" if held_out else "seen",
                "holdout_reason": (
                    f"withhold ordinal-direction composition {demonstrated}" if held_out else ""
                ),
            }
        )
        rows.append(row)
    choose_ordering_assignment(rows)
    return rows


COUNTING_OBJECTS = {
    "B": ("blue_pen", "blue pen"),
    "Y": ("yellow_block", "yellow block"),
    "G": ("green_pencil_sharpener", "green pencil sharpener"),
    "A": ("airplane_without_propellers", "airplane toy without propellers"),
}


def parse_counting_items(raw: str) -> list[str]:
    raw = re.sub(r"\s+\((?:Top|Side|Hidden)\)", "", raw, flags=re.IGNORECASE)
    if not raw or raw.lower().strip() == "empty":
        return []
    return [COUNTING_OBJECTS[token.strip()][0] for token in raw.split(",") if token.strip()]


def counting_transition(local_episode: int) -> tuple[int, int, str]:
    transitions = (
        (0, 7, 0, 1, "into"),
        (8, 15, 1, 2, "into"),
        (16, 24, 2, 3, "into"),
        (25, 30, 1, 0, "out"),
        (31, 36, 2, 1, "out"),
        (37, 42, 3, 2, "out"),
        (43, 49, 4, 3, "out"),
    )
    for start, end, initial, final, direction in transitions:
        if start <= local_episode <= end:
            return initial, final, direction
    raise ValueError(f"Unknown counting local episode: {local_episode}")


def parse_counting(reader: Any) -> list[dict[str, Any]]:
    pages = PageRange(reader, range(56, 64))
    entry = re.compile(r"\[(\d{3})\]\s+(Home|Post-Drop|Recovery)\s+\|\s+")
    matches = list(entry.finditer(pages.text))
    targets = (
        COUNTING_OBJECTS["B"],
        COUNTING_OBJECTS["Y"],
        COUNTING_OBJECTS["G"],
        COUNTING_OBJECTS["A"],
    )
    rows: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        episode = int(match.group(1))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(pages.text)
        raw = pages.text[match.end() : end]
        raw = re.split(
            r"\s+(?:\d+\s*->\s*\d+|PROMPT:|PART\s+\d+:|={3,}|-{3,})",
            raw,
            maxsplit=1,
        )[0].strip()
        bowl_raw = ""
        table_raw = ""
        if raw.startswith("Bowl:"):
            bowl_part, table_part = raw.split("| Table:", 1)
            bowl_raw = bowl_part.removeprefix("Bowl:").strip()
            table_raw = table_part.strip()
        elif raw.startswith("Table:"):
            table_raw = raw.removeprefix("Table:").strip()
        else:
            raise ValueError(f"Cannot parse counting episode {episode}: {raw!r}")
        bowl = parse_counting_items(bowl_raw)
        table = parse_counting_items(table_raw)
        target_id, target_name = targets[episode // 50]
        initial, final, direction = counting_transition(episode % 50)
        held_out = final in {1, 3}
        row = base_record(
            "counting",
            episode,
            pages.page_at(match.start()),
            {
                "Home": "home",
                "Post-Drop": "post_drop",
                "Recovery": "recovery",
            }[match.group(2)],
            target_id,
            target_name,
            "object",
        )
        row.update(
            {
                "scene_objects_json": json.dumps(bowl + table),
                "scene_attributes_json": json.dumps({"bowl": bowl, "table": table}, sort_keys=True),
                "scene_size": len(bowl) + len(table),
                "initial_count": initial,
                "final_count": final,
                "action_direction": direction,
                "demonstrated_concept": f"count_{final}",
                "assigned_concept": (f"object_identity_{direction}" if held_out else f"count_{final}"),
                "semantic_cell": "held_out" if held_out else "seen",
                "holdout_reason": (f"withhold final-count goal {final}" if held_out else ""),
                "prompt_type": "identity" if held_out else "semantic_reasoning",
            }
        )
        rows.append(row)
    return rows


def read_source_metadata(cache_root: Path) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise RuntimeError("pyarrow is required to validate Hugging Face parquet metadata") from exc

    episodes: dict[tuple[str, int], dict[str, Any]] = {}
    provenance: dict[str, Any] = {}
    for source in SOURCES:
        snapshot = (
            cache_root / f"datasets--justintiensmith--{source.repo_name}" / "snapshots" / source.revision
        )
        info_path = snapshot / "meta" / "info.json"
        episode_files = sorted((snapshot / "meta" / "episodes").rglob("*.parquet"))
        if not info_path.exists() or not episode_files:
            raise FileNotFoundError(f"Metadata snapshot is incomplete for {source.repo_id}: {snapshot}")
        info = json.loads(info_path.read_text())
        row_count = 0
        for episode_file in episode_files:
            table = parquet.read_table(episode_file, columns=["episode_index", "tasks", "length"])
            for episode_index, tasks, length in zip(
                table["episode_index"].to_pylist(),
                table["tasks"].to_pylist(),
                table["length"].to_pylist(),
                strict=True,
            ):
                episodes[(source.repo_id, int(episode_index))] = {
                    "source_task": " || ".join(tasks),
                    "source_episode_length": int(length),
                }
                row_count += 1
        provenance[source.repo_id] = {
            "revision": source.revision,
            "codebase_version": info.get("codebase_version"),
            "robot_type": info.get("robot_type"),
            "fps": info.get("fps"),
            "total_episodes": info.get("total_episodes"),
            "total_frames": info.get("total_frames"),
            "total_tasks": info.get("total_tasks"),
            "metadata_rows_read": row_count,
        }
    return episodes, provenance


def join_source_metadata(
    records: list[dict[str, Any]], source_metadata: dict[tuple[str, int], dict[str, Any]]
) -> None:
    for record in records:
        key = (record["source_repo_id"], record["source_episode_index"])
        if key not in source_metadata:
            raise KeyError(f"No source metadata for {key}")
        record.update(source_metadata[key])
        flags = json.loads(record["annotation_flags_json"])
        source_task = record["source_task"].lower()
        if (
            record["task_family"] == "size_recognition"
            and record["target_id"] == "green_block"
            and "green block sharpener" in source_task
        ):
            flags.append("source_task_green_block_sharpener_typo")
        if (
            record["task_family"] == "state_recognition"
            and record["target_category"] == "brown cup"
            and source_task
            not in {
                "put a brown cup in the bowl.",
                "pick up the brown cup and place it into the bowl.",
            }
        ):
            flags.append("unexpected_source_task")
        record["annotation_flags_json"] = json.dumps(sorted(set(flags)))


SIZE_TEMPLATES = {
    "smallest": (
        "Put the smallest object in the bowl.",
        "Pick up the smallest item and place it in the bowl.",
        "Move the object that is smallest into the bowl.",
    ),
    "largest": (
        "Put the largest object in the bowl.",
        "Pick up the largest item and place it in the bowl.",
        "Move the object that is largest into the bowl.",
    ),
}

IDENTITY_IN_TEMPLATES = (
    "Put the {target} in the bowl.",
    "Pick up the {target} and place it in the bowl.",
    "Move the {target} into the bowl.",
)

IDENTITY_OUT_TEMPLATES = (
    "Take the {target} out of the bowl.",
    "Remove the {target} from the bowl.",
    "Move the {target} from the bowl to the table.",
)

STATE_FULL_TEMPLATES = (
    "Put the {state}, {orientation} {category} in the bowl.",
    "Pick up the {category} that is {state} and {orientation}, then place it in the bowl.",
    "Move the {state} {category} that is {orientation} into the bowl.",
)

STATE_PARTIAL_TEMPLATES = {
    "closed": (
        "Put the closed {category} in the bowl.",
        "Pick up the {category} that is closed and place it in the bowl.",
        "Move the closed {category} into the bowl.",
    ),
    "upside_down": (
        "Put the upside-down {category} in the bowl.",
        "Pick up the {category} that is upside-down and place it in the bowl.",
        "Move the inverted {category} into the bowl.",
    ),
}

RELATION_TEMPLATES = {
    "front": (
        "Place the {target} in front of the {reference}.",
        "Move the {target} to the front of the {reference}.",
        "Put the {target} on the table in front of the {reference}.",
    ),
    "behind": (
        "Place the {target} behind the {reference}.",
        "Move the {target} to the back of the {reference}.",
        "Put the {target} on the table behind the {reference}.",
    ),
    "next_to": (
        "Place the {target} next to the {reference}.",
        "Move the {target} beside the {reference}.",
        "Put the {target} on the table adjacent to the {reference}.",
    ),
}

REFERENTIAL_TEMPLATES = {
    "closest": (
        "Put the {category} closest to the {reference} in the bowl.",
        "Pick up the {category} nearest to the {reference} and place it in the bowl.",
        "Move the {category} that is closest to the {reference} into the bowl.",
    ),
    "between": (
        "Put the {category} between the {reference_a} and the {reference_b} in the bowl.",
        "Pick up the {category} positioned between the {reference_a} and the "
        "{reference_b}, then place it in the bowl.",
        "Move the {category} lying between the {reference_a} and the {reference_b} into the bowl.",
    ),
}

ORDERING_TEMPLATES = (
    "Put the {ordinal} object from the {side} in the bowl.",
    "Pick up the object that is {ordinal} from the {side} and place it in the bowl.",
    "Move the {ordinal} item counted from the {side} into the bowl.",
)

COUNTING_TEMPLATES = {
    0: (
        "Make the bowl contain exactly zero objects.",
        "Leave no objects in the bowl.",
        "Adjust the bowl so that it contains zero objects.",
    ),
    2: (
        "Make the bowl contain exactly two objects.",
        "Leave exactly two objects in the bowl.",
        "Adjust the bowl so that it contains two objects.",
    ),
}


def prompt_templates(record: dict[str, Any]) -> tuple[str, ...]:
    family = record["task_family"]
    concept = record["assigned_concept"]
    if record["prompt_type"] == "identity":
        if family == "counting" and record["action_direction"] == "out":
            return IDENTITY_OUT_TEMPLATES
        return IDENTITY_IN_TEMPLATES
    if family == "size_recognition":
        return SIZE_TEMPLATES[concept]
    if family == "state_recognition":
        if record["prompt_type"] == "semantic_partial":
            return STATE_PARTIAL_TEMPLATES[concept]
        return STATE_FULL_TEMPLATES
    if family == "relational_placement":
        return RELATION_TEMPLATES[concept]
    if family == "referential_disambiguation":
        return REFERENTIAL_TEMPLATES[concept]
    if family == "ordering":
        return ORDERING_TEMPLATES
    if family == "counting":
        return COUNTING_TEMPLATES[int(record["final_count"])]
    raise ValueError(f"No templates for {family}")


def render_prompt(record: dict[str, Any], template: str) -> str:
    orientation = str(record["orientation"]).replace("_", "-")
    state = str(record["state"]).replace("_", "-")
    reference_names = record.get("_reference_names", [])
    values = {
        "target": record["target_name"],
        "category": record["target_category"],
        "state": state,
        "orientation": orientation,
        "reference": reference_names[0] if reference_names else "",
        "reference_a": reference_names[0] if reference_names else "",
        "reference_b": reference_names[1] if len(reference_names) > 1 else "",
    }
    if record["task_family"] == "ordering" and record["assigned_concept"] != "object_identity":
        ordinal, side = record["assigned_concept"].split("_from_")
        values.update({"ordinal": ordinal, "side": side})
    return template.format(**values)


def assign_prompts(records: list[dict[str, Any]]) -> None:
    groups: defaultdict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        identity_target = record["target_id"] if record["prompt_type"] == "identity" else ""
        direction = record["action_direction"] if record["prompt_type"] == "identity" else ""
        key = (
            record["task_family"],
            record["assigned_concept"],
            identity_target,
            direction,
        )
        groups[key].append(record)
    for _key, group in groups.items():
        group.sort(
            key=lambda record: stable_digest(
                record["global_episode_id"],
                record["start_type"],
                record["scene_objects_json"],
            )
        )
        for index, record in enumerate(group):
            templates = prompt_templates(record)
            template_index = index % len(templates)
            record["template_id"] = (
                f"{record['task_family']}.{record['assigned_concept']}.{template_index + 1}"
            )
            record["assigned_prompt"] = render_prompt(record, templates[template_index])


def validate_records(records: list[dict[str, Any]], provenance: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if len(records) != 1200:
        errors.append(f"Expected 1200 rows, found {len(records)}")
    global_ids = [record["global_episode_id"] for record in records]
    if len(set(global_ids)) != len(global_ids):
        errors.append("global_episode_id is not unique")

    family_summary: dict[str, Any] = {}
    for source in SOURCES:
        family_rows = [record for record in records if record["task_family"] == source.task_family]
        indices = sorted(record["source_episode_index"] for record in family_rows)
        if indices != list(range(200)):
            errors.append(f"{source.task_family}: episode indices are not exactly 0..199")
        split_counts = Counter(record["recommended_split"] for record in family_rows)
        if split_counts != Counter({"train": 200}):
            errors.append(
                f"{source.task_family}: expected all 200 episodes in train, got {dict(split_counts)}"
            )
        semantic_counts = Counter(record["semantic_cell"] for record in family_rows)
        prompt_counts = Counter(record["prompt_type"] for record in family_rows)
        concept_counts = Counter(record["demonstrated_concept"] for record in family_rows)
        template_counts = Counter(record["template_id"] for record in family_rows)
        family_summary[source.task_family] = {
            "rows": len(family_rows),
            "verified_object_inventory": VERIFIED_OBJECT_INVENTORY[source.task_family],
            "semantic_cells": dict(sorted(semantic_counts.items())),
            "prompt_types": dict(sorted(prompt_counts.items())),
            "demonstrated_concepts": dict(sorted(concept_counts.items())),
            "templates": dict(sorted(template_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
        }
        for record in family_rows:
            scene = json.loads(record["scene_objects_json"])
            references = json.loads(record["reference_ids_json"])
            if record["target_id"] not in scene:
                errors.append(f"{record['global_episode_id']}: target is absent from scene")
            missing_references = [ref for ref in references if ref not in scene]
            if missing_references:
                errors.append(
                    f"{record['global_episode_id']}: references absent from scene: {missing_references}"
                )
            if not record["assigned_prompt"]:
                errors.append(f"{record['global_episode_id']}: assigned_prompt is empty")
            if not isinstance(record["source_episode_length"], int) or record["source_episode_length"] <= 0:
                errors.append(f"{record['global_episode_id']}: invalid source episode length")

        expected_inventory = set(VERIFIED_OBJECT_INVENTORY[source.task_family])
        scene_inventory = {
            object_id for record in family_rows for object_id in json.loads(record["scene_objects_json"])
        }
        target_inventory = {record["target_id"] for record in family_rows}
        if scene_inventory != expected_inventory:
            errors.append(
                f"{source.task_family}: scene inventory {sorted(scene_inventory)} "
                f"does not match verified inventory {sorted(expected_inventory)}"
            )
        if target_inventory != expected_inventory:
            errors.append(
                f"{source.task_family}: target inventory {sorted(target_inventory)} "
                f"does not match verified inventory {sorted(expected_inventory)}"
            )

    expected_concepts = {
        "size_recognition": Counter({"smallest": 100, "largest": 100}),
        "relational_placement": Counter({"front": 48, "behind": 52, "left": 48, "right": 52}),
        "referential_disambiguation": Counter({"closest": 60, "furthest": 60, "between": 80}),
        "counting": Counter({"count_0": 24, "count_1": 56, "count_2": 56, "count_3": 64}),
    }
    for family, expected in expected_concepts.items():
        actual = Counter(
            record["demonstrated_concept"] for record in records if record["task_family"] == family
        )
        if actual != expected:
            errors.append(f"{family}: unexpected concept balance {dict(actual)}, expected {dict(expected)}")

    for record in records:
        prompt = normalize_text(record["assigned_prompt"]).lower()
        family = record["task_family"]
        if (
            family == "size_recognition"
            and (
                record["target_id"],
                record["demonstrated_concept"],
            )
            in {("green_block", "largest"), ("juggling_ball", "smallest")}
            and record["prompt_type"] != "identity"
        ):
            errors.append(f"{record['global_episode_id']}: size held-out cell is not identity-labeled")
        elif family == "state_recognition":
            if "closed" in prompt and ("upside-down" in prompt or "inverted" in prompt):
                errors.append(f"{record['global_episode_id']}: held-out state conjunction leaked")
        elif family == "relational_placement":
            if re.search(r"\b(?:left|right)\b", prompt):
                errors.append(f"{record['global_episode_id']}: directed horizontal relation leaked")
        elif family == "referential_disambiguation":
            if re.search(r"\b(?:furthest|farthest)\b|most distant", prompt):
                errors.append(f"{record['global_episode_id']}: furthest synonym leaked")
        elif family == "ordering":
            if re.search(r"\bfirst\b.*\bright\b|\brightmost\b", prompt):
                errors.append(f"{record['global_episode_id']}: first-from-right leaked")
            if re.search(r"\bthird\b.*\bleft\b", prompt):
                errors.append(f"{record['global_episode_id']}: third-from-left leaked")
            if record["assigned_concept"] != "object_identity":
                ordinal, side = record["assigned_concept"].split("_from_")
                expected_slot = (
                    int(record["target_slot_left"]) if side == "left" else int(record["target_slot_right"])
                )
                if ORDINALS[expected_slot] != ordinal:
                    errors.append(f"{record['global_episode_id']}: assigned ordering prompt is false")
        elif (
            family == "counting"
            and record["semantic_cell"] == "held_out"
            and re.search(r"\b(?:one|three)\b", prompt)
        ):
            errors.append(f"{record['global_episode_id']}: held-out count leaked")
        if family == "counting":
            locations = json.loads(record["scene_attributes_json"])
            bowl = locations["bowl"]
            table = locations["table"]
            if len(bowl) != int(record["initial_count"]):
                errors.append(f"{record['global_episode_id']}: bowl occupancy disagrees with initial_count")
            if record["action_direction"] == "into":
                if record["target_id"] not in table or record["target_id"] in bowl:
                    errors.append(f"{record['global_episode_id']}: into target is not exclusively on table")
            elif record["target_id"] not in bowl:
                errors.append(f"{record['global_episode_id']}: out target is absent from bowl")

    state_ambiguities = [
        record["global_episode_id"]
        for record in records
        if any(flag.endswith("_not_unique") for flag in json.loads(record["annotation_flags_json"]))
    ]
    if state_ambiguities:
        warnings.append(f"{len(state_ambiguities)} state prompts require manual uniqueness review")

    source_flag_counts = Counter(
        flag for record in records for flag in json.loads(record["annotation_flags_json"])
    )
    if source_flag_counts:
        warnings.append("Source annotations contain normalized inconsistencies; see source_flag_counts")

    expected_provenance = {source.repo_id for source in SOURCES}
    if set(provenance) != expected_provenance:
        errors.append("Provenance does not cover all six source repositories")
    for repo_id, values in provenance.items():
        if values.get("total_episodes") != 200 or values.get("metadata_rows_read") != 200:
            errors.append(f"{repo_id}: source metadata does not contain 200 episodes")

    return {
        "manifest_version": MANIFEST_VERSION,
        "status": "passed" if not errors else "failed",
        "row_count": len(records),
        "unique_global_episode_ids": len(set(global_ids)),
        "errors": errors,
        "warnings": warnings,
        "source_flag_counts": dict(sorted(source_flag_counts.items())),
        "families": family_summary,
        "provenance": provenance,
    }


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {column: record.get(column, "") for column in MANIFEST_COLUMNS}


def write_outputs(
    output_dir: Path,
    records: list[dict[str, Any]],
    validation_report: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "prompt_manifest_v1.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(public_record(record) for record in records)
    jsonl_path = output_dir / "prompt_manifest_v1.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(public_record(record), sort_keys=True) + "\n")
    report_path = output_dir / "validation_report_v1.json"
    report_path.write_text(
        json.dumps(validation_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    inventory_path = output_dir / "object_inventory_v1.json"
    inventory_path.write_text(
        json.dumps(VERIFIED_OBJECT_INVENTORY, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument(
        "--hf-cache-root",
        type=Path,
        default=Path.home() / ".cache" / "huggingface" / "hub",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to parse the benchmark PDF") from exc

    reader = PdfReader(args.pdf)
    parser_functions: tuple[Callable[[Any], list[dict[str, Any]]], ...] = (
        parse_state,
        parse_relational,
        parse_referential,
        parse_ordering,
        parse_counting,
        parse_size,
    )
    records = [record for parser_function in parser_functions for record in parser_function(reader)]
    source_metadata, provenance = read_source_metadata(args.hf_cache_root)
    join_source_metadata(records, source_metadata)
    assign_prompts(records)
    records.sort(
        key=lambda record: (
            [source.task_family for source in SOURCES].index(record["task_family"]),
            record["source_episode_index"],
        )
    )
    validation_report = validate_records(records, provenance)
    write_outputs(args.output_dir, records, validation_report)
    print(json.dumps(validation_report, indent=2, sort_keys=True))
    if validation_report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
