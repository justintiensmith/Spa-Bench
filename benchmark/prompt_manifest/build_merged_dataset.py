#!/usr/bin/env python3

"""Build a non-destructive, prompt-labeled merge of the six VLA datasets.

The builder downloads immutable source revisions, copies their LeRobot v3.0
data and video files into a new dataset, rewrites episode/frame indices, and
replaces each episode's task with the assigned prompt from prompt_manifest_v1.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import snapshot_download


@dataclass(frozen=True)
class SourceSpec:
    task_family: str
    repo_id: str
    revision: str


SOURCES = (
    SourceSpec(
        "state_recognition",
        "justintiensmith/MT_State_Recognition_200",
        "168e12e735da9ad62716dca89cff660b53082cc3",
    ),
    SourceSpec(
        "relational_placement",
        "justintiensmith/SP_Relational_Placement_200",
        "8eff46af18af7a9a6f763ed975f8b3357c673685",
    ),
    SourceSpec(
        "referential_disambiguation",
        "justintiensmith/SP_Referential_Disambiguation_200",
        "2642784f74a0c91bc118702b7993895aacd311f5",
    ),
    SourceSpec(
        "ordering",
        "justintiensmith/SP_Sequencing_200",
        "1cda4c4c3c6ae1fa4b5dc6d2cf4c887bb9f1da4e",
    ),
    SourceSpec(
        "counting",
        "justintiensmith/SP_Counting_200",
        "6591c0f19952e23010b7c6a0630e4d60f8714cbb",
    ),
    SourceSpec(
        "size_recognition",
        "justintiensmith/MT_Size_Recognition_200",
        "3a6e75d91e8339a87eebd8e545d87b148ae19925",
    ),
)

EXPECTED_EPISODES_PER_SOURCE = 200
EXPECTED_TOTAL_EPISODES = 1200
EXPECTED_TOTAL_FRAMES = 615_537
QUANTILE_KEYS = ("q01", "q10", "q50", "q90", "q99")
QUANTILE_VALUES = {
    "q01": 0.01,
    "q10": 0.10,
    "q50": 0.50,
    "q90": 0.90,
    "q99": 0.99,
}


def load_manifest(path: Path) -> tuple[list[dict[str, str]], dict[tuple[str, int], dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != EXPECTED_TOTAL_EPISODES:
        raise ValueError(f"Expected {EXPECTED_TOTAL_EPISODES} manifest rows, found {len(rows)}")
    if Counter(row["recommended_split"] for row in rows) != Counter({"train": EXPECTED_TOTAL_EPISODES}):
        raise ValueError("Every manifest row must be assigned to train")

    keyed: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        key = (row["source_repo_id"], int(row["source_episode_index"]))
        if key in keyed:
            raise ValueError(f"Duplicate manifest source episode: {key}")
        if not row["assigned_prompt"].strip():
            raise ValueError(f"Empty assigned prompt for {key}")
        keyed[key] = row

    for spec in SOURCES:
        source_rows = [row for row in rows if row["source_repo_id"] == spec.repo_id]
        indices = sorted(int(row["source_episode_index"]) for row in source_rows)
        revisions = {row["source_revision"] for row in source_rows}
        if indices != list(range(EXPECTED_EPISODES_PER_SOURCE)):
            raise ValueError(f"{spec.repo_id} does not contain manifest episodes 0..199")
        if revisions != {spec.revision}:
            raise ValueError(f"{spec.repo_id} manifest revision does not match the pinned revision")

    return rows, keyed


def resolve_sources(offline: bool) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for source_number, spec in enumerate(SOURCES, start=1):
        print(f"[{source_number}/6] resolving {spec.repo_id}@{spec.revision}", flush=True)
        root = snapshot_download(
            repo_id=spec.repo_id,
            repo_type="dataset",
            revision=spec.revision,
            local_files_only=offline,
            max_workers=8,
        )
        roots[spec.repo_id] = Path(root)
    return roots


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_episode_rows(root: Path) -> list[dict[str, Any]]:
    paths = sorted((root / "meta" / "episodes").rglob("*.parquet"))
    if not paths:
        raise FileNotFoundError(f"No episode metadata under {root}")
    rows = [row for path in paths for row in pq.read_table(path).to_pylist()]
    return sorted(rows, key=lambda row: int(row["episode_index"]))


def validate_source_compatibility(
    roots: dict[str, Path],
    manifest_by_source: dict[tuple[str, int], dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    infos: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    episodes_by_repo: dict[str, list[dict[str, Any]]] = {}

    for spec in SOURCES:
        root = roots[spec.repo_id]
        info = read_json(root / "meta" / "info.json")
        episodes = load_episode_rows(root)
        if info["codebase_version"] != "v3.0":
            raise ValueError(f"{spec.repo_id} is not LeRobot v3.0")
        if info["total_episodes"] != EXPECTED_EPISODES_PER_SOURCE:
            raise ValueError(f"{spec.repo_id} does not contain exactly 200 episodes")
        if len(episodes) != EXPECTED_EPISODES_PER_SOURCE:
            raise ValueError(f"{spec.repo_id} episode metadata does not contain 200 rows")
        if [int(row["episode_index"]) for row in episodes] != list(range(EXPECTED_EPISODES_PER_SOURCE)):
            raise ValueError(f"{spec.repo_id} episode metadata indices are not 0..199")
        for row in episodes:
            episode_index = int(row["episode_index"])
            manifest_row = manifest_by_source[(spec.repo_id, episode_index)]
            if int(row["length"]) != int(manifest_row["source_episode_length"]):
                raise ValueError(f"{spec.repo_id} episode {episode_index} length disagrees with the manifest")

        infos.append(info)
        episodes_by_repo[spec.repo_id] = episodes
        provenance.append(
            {
                "task_family": spec.task_family,
                "repo_id": spec.repo_id,
                "revision": spec.revision,
                "episodes": info["total_episodes"],
                "frames": info["total_frames"],
            }
        )

    base_info = infos[0]
    for spec, info in zip(SOURCES, infos, strict=True):
        for key in ("fps", "robot_type", "features"):
            if info[key] != base_info[key]:
                raise ValueError(f"{spec.repo_id} has an incompatible {key}")
    if sum(info["total_frames"] for info in infos) != EXPECTED_TOTAL_FRAMES:
        raise ValueError("Pinned source frame totals do not sum to 615,537")
    return base_info, provenance, episodes_by_repo


def allocate_file(counter: int, chunk_size: int) -> tuple[int, int]:
    return counter // chunk_size, counter % chunk_size


def format_data_path(info: dict[str, Any], chunk_index: int, file_index: int) -> Path:
    return Path(info["data_path"].format(chunk_index=chunk_index, file_index=file_index))


def format_video_path(
    info: dict[str, Any],
    video_key: str,
    chunk_index: int,
    file_index: int,
) -> Path:
    return Path(
        info["video_path"].format(
            video_key=video_key,
            chunk_index=chunk_index,
            file_index=file_index,
        )
    )


def replace_column(table: pa.Table, name: str, values: np.ndarray) -> pa.Table:
    column_index = table.schema.get_field_index(name)
    if column_index < 0:
        raise KeyError(f"Missing required data column: {name}")
    column_type = table.schema.field(column_index).type
    return table.set_column(column_index, name, pa.array(values, type=column_type))


def write_episode_row_groups(table: pa.Table, path: Path) -> None:
    episode_indices = table["episode_index"].combine_chunks().to_numpy(zero_copy_only=False)
    if len(episode_indices) == 0:
        raise ValueError(f"Refusing to write empty data file: {path}")
    boundaries = np.flatnonzero(episode_indices[1:] != episode_indices[:-1]) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [len(episode_indices)]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with pq.ParquetWriter(path, table.schema, compression="snappy", use_dictionary=True) as writer:
        for start, end in zip(starts, ends, strict=True):
            writer.write_table(table.slice(int(start), int(end - start)))


def copy_file(source: Path, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_size = source.stat().st_size
    if destination.stat().st_size != source_size:
        raise OSError(f"Copied file size mismatch for {destination}")
    return source_size


def rewrite_data(
    build_root: Path,
    roots: dict[str, Path],
    infos: dict[str, dict[str, Any]],
    episodes_by_repo: dict[str, list[dict[str, Any]]],
    task_indices_by_repo: dict[str, np.ndarray],
    episode_offsets: dict[str, int],
    frame_offsets: dict[str, int],
) -> tuple[
    dict[str, dict[tuple[int, int], tuple[int, int]]],
    list[dict[str, Any]],
]:
    data_mappings: dict[str, dict[tuple[int, int], tuple[int, int]]] = {}
    written_files: list[dict[str, Any]] = []
    file_counter = 0
    chunk_size = int(next(iter(infos.values()))["chunks_size"])

    for spec in SOURCES:
        info = infos[spec.repo_id]
        root = roots[spec.repo_id]
        source_pairs = sorted(
            {
                (int(row["data/chunk_index"]), int(row["data/file_index"]))
                for row in episodes_by_repo[spec.repo_id]
            }
        )
        mapping: dict[tuple[int, int], tuple[int, int]] = {}
        source_frame_count = 0

        for source_pair in source_pairs:
            destination_pair = allocate_file(file_counter, chunk_size)
            file_counter += 1
            mapping[source_pair] = destination_pair
            source_path = root / format_data_path(info, *source_pair)
            destination_path = build_root / format_data_path(info, *destination_pair)

            table = pq.read_table(source_path)
            local_episode_indices = (
                table["episode_index"].combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
            )
            local_indices = table["index"].combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
            if np.any(local_episode_indices < 0) or np.any(
                local_episode_indices >= EXPECTED_EPISODES_PER_SOURCE
            ):
                raise ValueError(f"{source_path} contains an invalid source episode index")

            table = replace_column(
                table,
                "episode_index",
                local_episode_indices + episode_offsets[spec.repo_id],
            )
            table = replace_column(
                table,
                "index",
                local_indices + frame_offsets[spec.repo_id],
            )
            table = replace_column(
                table,
                "task_index",
                task_indices_by_repo[spec.repo_id][local_episode_indices],
            )
            write_episode_row_groups(table, destination_path)
            source_frame_count += table.num_rows
            written_files.append(
                {
                    "source_repo_id": spec.repo_id,
                    "source_path": str(source_path.relative_to(root)),
                    "destination_path": str(destination_path.relative_to(build_root)),
                    "rows": table.num_rows,
                    "bytes": destination_path.stat().st_size,
                }
            )

        if source_frame_count != int(info["total_frames"]):
            raise ValueError(f"{spec.repo_id} data rows {source_frame_count} != {info['total_frames']}")
        data_mappings[spec.repo_id] = mapping

    return data_mappings, written_files


def copy_videos(
    build_root: Path,
    roots: dict[str, Path],
    infos: dict[str, dict[str, Any]],
    episodes_by_repo: dict[str, list[dict[str, Any]]],
    copy_workers: int,
) -> tuple[
    dict[str, dict[str, dict[tuple[int, int], tuple[int, int]]]],
    list[dict[str, Any]],
]:
    base_info = next(iter(infos.values()))
    video_keys = [key for key, feature in base_info["features"].items() if feature["dtype"] == "video"]
    chunk_size = int(base_info["chunks_size"])
    file_counters = dict.fromkeys(video_keys, 0)
    mappings: dict[str, dict[str, dict[tuple[int, int], tuple[int, int]]]] = {}
    copy_jobs: list[tuple[Path, Path, dict[str, Any]]] = []

    for spec in SOURCES:
        info = infos[spec.repo_id]
        root = roots[spec.repo_id]
        mappings[spec.repo_id] = {}
        for video_key in video_keys:
            source_pairs = sorted(
                {
                    (
                        int(row[f"videos/{video_key}/chunk_index"]),
                        int(row[f"videos/{video_key}/file_index"]),
                    )
                    for row in episodes_by_repo[spec.repo_id]
                }
            )
            key_mapping: dict[tuple[int, int], tuple[int, int]] = {}
            for source_pair in source_pairs:
                destination_pair = allocate_file(file_counters[video_key], chunk_size)
                file_counters[video_key] += 1
                key_mapping[source_pair] = destination_pair
                source_path = root / format_video_path(info, video_key, *source_pair)
                destination_path = build_root / format_video_path(info, video_key, *destination_pair)
                record = {
                    "source_repo_id": spec.repo_id,
                    "video_key": video_key,
                    "source_path": str(source_path.relative_to(root)),
                    "destination_path": str(destination_path.relative_to(build_root)),
                    "bytes": source_path.stat().st_size,
                }
                copy_jobs.append((source_path, destination_path, record))
            mappings[spec.repo_id][video_key] = key_mapping

    print(f"Copying {len(copy_jobs)} video files with {copy_workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=copy_workers) as executor:
        sizes = list(
            executor.map(
                lambda job: copy_file(job[0], job[1]),
                copy_jobs,
            )
        )
    records = []
    for (_, _, record), copied_size in zip(copy_jobs, sizes, strict=True):
        if copied_size != record["bytes"]:
            raise OSError(f"Video copy size mismatch for {record['destination_path']}")
        records.append(record)
    return mappings, records


def set_constant_episode_stats(row: dict[str, Any], feature: str, value: int) -> None:
    for stat_name in ("min", "max", "mean", *QUANTILE_KEYS):
        key = f"stats/{feature}/{stat_name}"
        if key in row:
            row[key] = [float(value)]
    std_key = f"stats/{feature}/std"
    if std_key in row:
        row[std_key] = [0.0]


def set_sequence_episode_stats(
    row: dict[str, Any],
    feature: str,
    values: np.ndarray,
) -> None:
    row[f"stats/{feature}/min"] = [float(values.min())]
    row[f"stats/{feature}/max"] = [float(values.max())]
    row[f"stats/{feature}/mean"] = [float(values.mean())]
    row[f"stats/{feature}/std"] = [float(values.std())]
    row[f"stats/{feature}/count"] = [int(values.size)]
    for key, quantile in QUANTILE_VALUES.items():
        stat_key = f"stats/{feature}/{key}"
        if stat_key in row:
            row[stat_key] = [float(np.quantile(values, quantile))]


def rewrite_episode_metadata(
    build_root: Path,
    base_info: dict[str, Any],
    roots: dict[str, Path],
    episodes_by_repo: dict[str, list[dict[str, Any]]],
    manifest_by_source: dict[tuple[str, int], dict[str, str]],
    task_indices_by_repo: dict[str, np.ndarray],
    episode_offsets: dict[str, int],
    frame_offsets: dict[str, int],
    data_mappings: dict[str, dict[tuple[int, int], tuple[int, int]]],
    video_mappings: dict[str, dict[str, dict[tuple[int, int], tuple[int, int]]]],
) -> list[dict[str, Any]]:
    video_keys = [key for key, feature in base_info["features"].items() if feature["dtype"] == "video"]
    merged_rows: list[dict[str, Any]] = []

    for spec in SOURCES:
        for source_row in episodes_by_repo[spec.repo_id]:
            row = copy.deepcopy(source_row)
            local_episode_index = int(row["episode_index"])
            merged_episode_index = episode_offsets[spec.repo_id] + local_episode_index
            merged_task_index = int(task_indices_by_repo[spec.repo_id][local_episode_index])
            prompt = manifest_by_source[(spec.repo_id, local_episode_index)]["assigned_prompt"]

            source_data_pair = (
                int(row["data/chunk_index"]),
                int(row["data/file_index"]),
            )
            destination_data_pair = data_mappings[spec.repo_id][source_data_pair]
            row["episode_index"] = merged_episode_index
            row["tasks"] = [prompt]
            row["data/chunk_index"], row["data/file_index"] = destination_data_pair
            row["dataset_from_index"] = int(row["dataset_from_index"]) + frame_offsets[spec.repo_id]
            row["dataset_to_index"] = int(row["dataset_to_index"]) + frame_offsets[spec.repo_id]
            row["meta/episodes/chunk_index"] = 0
            row["meta/episodes/file_index"] = 0

            for video_key in video_keys:
                source_video_pair = (
                    int(row[f"videos/{video_key}/chunk_index"]),
                    int(row[f"videos/{video_key}/file_index"]),
                )
                destination_video_pair = video_mappings[spec.repo_id][video_key][source_video_pair]
                row[f"videos/{video_key}/chunk_index"] = destination_video_pair[0]
                row[f"videos/{video_key}/file_index"] = destination_video_pair[1]

            set_constant_episode_stats(row, "episode_index", merged_episode_index)
            set_constant_episode_stats(row, "task_index", merged_task_index)
            global_indices = np.arange(
                row["dataset_from_index"],
                row["dataset_to_index"],
                dtype=np.float64,
            )
            set_sequence_episode_stats(row, "index", global_indices)
            merged_rows.append(row)

    merged_rows.sort(key=lambda row: int(row["episode_index"]))
    if [int(row["episode_index"]) for row in merged_rows] != list(range(EXPECTED_TOTAL_EPISODES)):
        raise ValueError("Merged episode metadata indices are not 0..1199")

    # Preserve the exact nested LeRobot episode-metadata schema.
    schema_path = sorted((roots[SOURCES[0].repo_id] / "meta" / "episodes").rglob("*.parquet"))[0]
    table = pa.Table.from_pylist(merged_rows, schema=pq.read_schema(schema_path))
    destination = build_root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, destination, compression="snappy", use_dictionary=True)
    return merged_rows


def aggregate_feature_stats(feature_stats: list[dict[str, Any]]) -> dict[str, Any]:
    means = np.stack([np.asarray(stats["mean"]) for stats in feature_stats])
    variances = np.stack([np.asarray(stats["std"]) ** 2 for stats in feature_stats])
    counts = np.stack([np.asarray(stats["count"]) for stats in feature_stats])
    total_count = counts.sum(axis=0)
    broadcast_counts = counts
    while broadcast_counts.ndim < means.ndim:
        broadcast_counts = np.expand_dims(broadcast_counts, axis=-1)

    total_mean = (means * broadcast_counts).sum(axis=0) / total_count
    delta_means = means - total_mean
    total_variance = ((variances + delta_means**2) * broadcast_counts).sum(axis=0) / total_count
    aggregated: dict[str, Any] = {
        "min": np.min(np.stack([np.asarray(stats["min"]) for stats in feature_stats]), axis=0),
        "max": np.max(np.stack([np.asarray(stats["max"]) for stats in feature_stats]), axis=0),
        "mean": total_mean,
        "std": np.sqrt(total_variance),
        "count": total_count,
    }
    for key in QUANTILE_KEYS:
        if all(key in stats for stats in feature_stats):
            values = np.stack([np.asarray(stats[key]) for stats in feature_stats])
            aggregated[key] = (values * broadcast_counts).sum(axis=0) / total_count
    return aggregated


def serialize_numpy(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: serialize_numpy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_numpy(item) for item in value]
    return value


def exact_scalar_stats(values: np.ndarray) -> dict[str, list[float] | list[int]]:
    result: dict[str, list[float] | list[int]] = {
        "min": [float(values.min())],
        "max": [float(values.max())],
        "mean": [float(values.mean())],
        "std": [float(values.std())],
        "count": [int(values.size)],
    }
    for key, quantile in QUANTILE_VALUES.items():
        result[key] = [float(np.quantile(values, quantile))]
    return result


def build_global_stats(
    roots: dict[str, Path],
    merged_rows: list[dict[str, Any]],
    task_indices_by_episode: np.ndarray,
) -> dict[str, Any]:
    source_stats = [read_json(roots[spec.repo_id] / "meta" / "stats.json") for spec in SOURCES]
    feature_keys = sorted({key for stats in source_stats for key in stats})
    merged_stats = {
        key: aggregate_feature_stats([stats[key] for stats in source_stats if key in stats])
        for key in feature_keys
    }

    episode_indices = np.concatenate(
        [np.full(int(row["length"]), int(row["episode_index"]), dtype=np.float64) for row in merged_rows]
    )
    task_indices = np.concatenate(
        [
            np.full(int(row["length"]), task_indices_by_episode[int(row["episode_index"])])
            for row in merged_rows
        ]
    ).astype(np.float64)
    global_indices = np.arange(EXPECTED_TOTAL_FRAMES, dtype=np.float64)
    merged_stats["episode_index"] = exact_scalar_stats(episode_indices)
    merged_stats["task_index"] = exact_scalar_stats(task_indices)
    merged_stats["index"] = exact_scalar_stats(global_indices)
    return serialize_numpy(merged_stats)


def write_tasks(build_root: Path, prompts: list[str]) -> dict[str, int]:
    unique_prompts = sorted(set(prompts))
    dataframe = pd.DataFrame(
        {"task_index": np.arange(len(unique_prompts), dtype=np.int64)},
        index=pd.Index(unique_prompts, name="task"),
    )
    path = build_root / "meta" / "tasks.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_parquet(path)
    return dict(zip(unique_prompts, range(len(unique_prompts)), strict=True))


def write_dataset_card(
    build_root: Path,
    output_repo_id: str,
    provenance: list[dict[str, Any]],
) -> None:
    source_lines = "\n".join(f"- `{item['repo_id']}` at `{item['revision']}`" for item in provenance)
    card = f"""---
license: apache-2.0
task_categories:
- robotics
tags:
- LeRobot
- VLA
- robotics
configs:
- config_name: default
  data_files: data/*/*.parquet
---

# Spa-Bench Prompted 1200

This is a non-destructive LeRobot v3.0 merge of six 200-episode benchmark
datasets. It contains 1,200 training episodes and 615,537 frames. Every
episode's task string is the assigned prompt from `meta/benchmark/prompt_manifest_v1.csv`.

The Coke and Pepsi objects are canonically labeled as a crushed Coke can and a
crushed Pepsi can. All rows are part of the training split.

## Immutable source revisions

{source_lines}

## Local identifier

`{output_repo_id}`
"""
    (build_root / "README.md").write_text(card, encoding="utf-8")


def validate_merged_dataset(
    build_root: Path,
    output_repo_id: str,
    manifest_by_source: dict[tuple[str, int], dict[str, str]],
    merged_rows: list[dict[str, Any]],
    task_index_by_prompt: dict[str, int],
    data_records: list[dict[str, Any]],
    video_records: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    info = read_json(build_root / "meta" / "info.json")
    tasks = pd.read_parquet(build_root / "meta" / "tasks.parquet")

    if info["total_episodes"] != EXPECTED_TOTAL_EPISODES:
        errors.append("info.json total_episodes is not 1200")
    if info["total_frames"] != EXPECTED_TOTAL_FRAMES:
        errors.append("info.json total_frames is not 615537")
    if info["splits"] != {"train": "0:1200"}:
        errors.append("info.json does not define the full dataset as train")
    if info["total_tasks"] != len(task_index_by_prompt):
        errors.append("info.json total_tasks disagrees with tasks.parquet")
    if len(merged_rows) != EXPECTED_TOTAL_EPISODES:
        errors.append("Episode metadata does not contain 1200 rows")

    expected_prompts_by_episode: dict[int, str] = {}
    episode_offset = 0
    for spec in SOURCES:
        for local_episode_index in range(EXPECTED_EPISODES_PER_SOURCE):
            expected_prompts_by_episode[episode_offset + local_episode_index] = manifest_by_source[
                (spec.repo_id, local_episode_index)
            ]["assigned_prompt"]
        episode_offset += EXPECTED_EPISODES_PER_SOURCE

    expected_from = 0
    for row in merged_rows:
        episode_index = int(row["episode_index"])
        expected_prompt = expected_prompts_by_episode[episode_index]
        if row["tasks"] != [expected_prompt]:
            errors.append(f"Episode {episode_index} task does not match its assigned prompt")
        if int(row["dataset_from_index"]) != expected_from:
            errors.append(f"Episode {episode_index} dataset_from_index is not contiguous")
        expected_from += int(row["length"])
        if int(row["dataset_to_index"]) != expected_from:
            errors.append(f"Episode {episode_index} dataset_to_index is incorrect")
    if expected_from != EXPECTED_TOTAL_FRAMES:
        errors.append("Episode lengths do not sum to 615537")

    total_data_rows = 0
    frame_counts: Counter[int] = Counter()
    seen_global_indices = np.zeros(EXPECTED_TOTAL_FRAMES, dtype=np.bool_)
    for record in data_records:
        path = build_root / record["destination_path"]
        table = pq.read_table(path, columns=["episode_index", "index", "task_index"])
        episode_values = (
            table["episode_index"].combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
        )
        index_values = table["index"].combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
        task_values = table["task_index"].combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
        total_data_rows += table.num_rows
        frame_counts.update(episode_values.tolist())
        expected_task_values = np.asarray(
            [
                task_index_by_prompt[expected_prompts_by_episode[int(episode_index)]]
                for episode_index in episode_values
            ],
            dtype=np.int64,
        )
        if not np.array_equal(task_values, expected_task_values):
            errors.append(f"{record['destination_path']} contains incorrect task indices")
        if len(index_values) and (np.any(index_values < 0) or np.any(index_values >= EXPECTED_TOTAL_FRAMES)):
            errors.append(f"{record['destination_path']} contains an invalid global index")
        elif len(index_values):
            if np.unique(index_values).size != index_values.size or np.any(seen_global_indices[index_values]):
                errors.append(f"{record['destination_path']} contains duplicate global indices")
            seen_global_indices[index_values] = True

    if total_data_rows != EXPECTED_TOTAL_FRAMES:
        errors.append(f"Data parquet rows total {total_data_rows}, not 615537")
    if not np.all(seen_global_indices):
        errors.append("Data parquet files do not cover every global index exactly once")
    for row in merged_rows:
        episode_index = int(row["episode_index"])
        if frame_counts[episode_index] != int(row["length"]):
            errors.append(f"Episode {episode_index} frame count disagrees with metadata")

    missing_videos = [
        record["destination_path"]
        for record in video_records
        if not (build_root / record["destination_path"]).is_file()
    ]
    if missing_videos:
        errors.append(f"{len(missing_videos)} referenced copied videos are missing")
    bad_video_sizes = [
        record["destination_path"]
        for record in video_records
        if (build_root / record["destination_path"]).stat().st_size != record["bytes"]
    ]
    if bad_video_sizes:
        errors.append(f"{len(bad_video_sizes)} copied videos have the wrong size")

    decoded_video_samples = 0
    try:
        import av
    except ImportError:
        warnings.append("PyAV is unavailable; video decode sampling was skipped")
    else:
        sample_records: dict[tuple[str, str], dict[str, Any]] = {}
        for record in video_records:
            sample_records.setdefault(
                (record["source_repo_id"], record["video_key"]),
                record,
            )
        for record in sample_records.values():
            path = build_root / record["destination_path"]
            try:
                with av.open(str(path)) as container:
                    frame = next(container.decode(video=0))
                if (frame.height, frame.width) != (480, 640):
                    errors.append(
                        f"{record['destination_path']} decoded at "
                        f"{frame.width}x{frame.height}, expected 640x480"
                    )
                decoded_video_samples += 1
            except Exception as exc:
                errors.append(f"{record['destination_path']} could not be decoded: {exc}")

    if set(tasks.index) != set(task_index_by_prompt):
        errors.append("tasks.parquet prompt set disagrees with the manifest")
    if len(task_index_by_prompt) != 350:
        warnings.append(f"Expected 350 unique prompts, found {len(task_index_by_prompt)}")

    report = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "repo_id": output_repo_id,
        "total_episodes": info["total_episodes"],
        "total_frames": info["total_frames"],
        "total_tasks": info["total_tasks"],
        "split": info["splits"],
        "data_files": len(data_records),
        "video_files": len(video_records),
        "video_bytes": sum(record["bytes"] for record in video_records),
        "decoded_video_samples": decoded_video_samples,
        "families": {spec.task_family: EXPECTED_EPISODES_PER_SOURCE for spec in SOURCES},
        "source_provenance": provenance,
    }
    return report


def build_dataset(
    manifest_path: Path,
    output_root: Path,
    output_repo_id: str,
    offline: bool,
    copy_workers: int,
) -> None:
    _, manifest_by_source = load_manifest(manifest_path)
    roots = resolve_sources(offline)
    base_info, provenance, episodes_by_repo = validate_source_compatibility(roots, manifest_by_source)
    infos = {spec.repo_id: read_json(roots[spec.repo_id] / "meta" / "info.json") for spec in SOURCES}

    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    build_root = output_root.with_name(f".{output_root.name}.building")
    if build_root.exists():
        raise FileExistsError(f"Previous partial build exists: {build_root}")
    build_root.mkdir(parents=True)

    prompts = [
        manifest_by_source[(spec.repo_id, episode_index)]["assigned_prompt"]
        for spec in SOURCES
        for episode_index in range(EXPECTED_EPISODES_PER_SOURCE)
    ]
    task_index_by_prompt = write_tasks(build_root, prompts)
    task_indices_by_repo = {
        spec.repo_id: np.asarray(
            [
                task_index_by_prompt[manifest_by_source[(spec.repo_id, episode_index)]["assigned_prompt"]]
                for episode_index in range(EXPECTED_EPISODES_PER_SOURCE)
            ],
            dtype=np.int64,
        )
        for spec in SOURCES
    }

    episode_offsets: dict[str, int] = {}
    frame_offsets: dict[str, int] = {}
    episode_offset = 0
    frame_offset = 0
    for spec in SOURCES:
        episode_offsets[spec.repo_id] = episode_offset
        frame_offsets[spec.repo_id] = frame_offset
        episode_offset += int(infos[spec.repo_id]["total_episodes"])
        frame_offset += int(infos[spec.repo_id]["total_frames"])

    print("Rewriting data parquet files", flush=True)
    data_mappings, data_records = rewrite_data(
        build_root,
        roots,
        infos,
        episodes_by_repo,
        task_indices_by_repo,
        episode_offsets,
        frame_offsets,
    )
    video_mappings, video_records = copy_videos(
        build_root,
        roots,
        infos,
        episodes_by_repo,
        copy_workers,
    )
    merged_rows = rewrite_episode_metadata(
        build_root,
        base_info,
        roots,
        episodes_by_repo,
        manifest_by_source,
        task_indices_by_repo,
        episode_offsets,
        frame_offsets,
        data_mappings,
        video_mappings,
    )

    info = copy.deepcopy(base_info)
    info["total_episodes"] = EXPECTED_TOTAL_EPISODES
    info["total_frames"] = EXPECTED_TOTAL_FRAMES
    info["total_tasks"] = len(task_index_by_prompt)
    info["splits"] = {"train": "0:1200"}
    write_json(build_root / "meta" / "info.json", info)

    task_indices_by_episode = np.asarray(
        [
            task_indices_by_repo[spec.repo_id][episode_index]
            for spec in SOURCES
            for episode_index in range(EXPECTED_EPISODES_PER_SOURCE)
        ],
        dtype=np.int64,
    )
    merged_stats = build_global_stats(roots, merged_rows, task_indices_by_episode)
    write_json(build_root / "meta" / "stats.json", merged_stats)

    benchmark_dir = build_root / "meta" / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    for artifact_name in (
        "prompt_manifest_v1.csv",
        "prompt_manifest_v1.jsonl",
        "validation_report_v1.json",
        "object_inventory_v1.json",
    ):
        artifact_path = manifest_path.parent / artifact_name
        if artifact_path.is_file():
            shutil.copy2(artifact_path, benchmark_dir / artifact_name)
    write_json(benchmark_dir / "source_revisions.json", provenance)
    write_dataset_card(build_root, output_repo_id, provenance)

    report = validate_merged_dataset(
        build_root,
        output_repo_id,
        manifest_by_source,
        merged_rows,
        task_index_by_prompt,
        data_records,
        video_records,
        provenance,
    )
    write_json(benchmark_dir / "merge_validation_report.json", report)
    if report["status"] != "passed":
        raise RuntimeError(f"Merged dataset validation failed; partial build retained at {build_root}")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    build_root.rename(output_root)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    print(f"Merged dataset ready at {output_root}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parent / "prompt_manifest_v1.csv",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path.home()
        / ".cache"
        / "huggingface"
        / "lerobot"
        / "justintiensmith"
        / "VLA_Benchmark_Prompted_1200",
    )
    parser.add_argument(
        "--output-repo-id",
        default="justintiensmith/VLA_Benchmark_Prompted_1200",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Require all six pinned source snapshots to already be in the local cache.",
    )
    parser.add_argument("--copy-workers", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.copy_workers < 1:
        raise ValueError("--copy-workers must be at least 1")
    build_dataset(
        manifest_path=args.manifest.resolve(),
        output_root=args.output_root.expanduser().resolve(),
        output_repo_id=args.output_repo_id,
        offline=args.offline,
        copy_workers=args.copy_workers,
    )


if __name__ == "__main__":
    main()
