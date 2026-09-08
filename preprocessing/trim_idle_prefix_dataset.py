#!/usr/bin/env python3
"""Create a LeRobot v3 dataset with per-episode idle prefixes omitted.

The source videos are copied byte-for-byte. Trimming is represented by shifting
each episode's video ``from_timestamp`` and removing matching rows from the
tabular data. Source camera/action length mismatches are reconciled to the
shortest stream. This avoids an unnecessary lossy video transcode while
producing the same logical dataset a decoder would see after physical trimming.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from lerobot.datasets.compute_stats import aggregate_stats, compute_episode_stats
from lerobot.datasets.io_utils import load_stats, write_stats

SOURCE_DATA_PATH = Path("data/chunk-000/file-000.parquet")
SOURCE_EPISODES_PATH = Path("meta/episodes/chunk-000/file-000.parquet")
OUTPUT_DATA_PATH = SOURCE_DATA_PATH
OUTPUT_EPISODES_PATH = SOURCE_EPISODES_PATH
AUDIT_DIR = Path("meta/trim_audit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output-repo", required=True)
    parser.add_argument("--motion-threshold", type=float, default=2.0)
    parser.add_argument("--baseline-frames", type=int, default=5)
    parser.add_argument("--sustain-frames", type=int, default=5)
    parser.add_argument("--pre-motion-frames", type=int, default=10)
    parser.add_argument(
        "--overlay-only",
        action="store_true",
        help="Write only files that must replace a server-side duplicate; do not copy videos/auxiliary metadata.",
    )
    return parser.parse_args()


def first_sustained_motion(
    actions: np.ndarray,
    *,
    threshold: float,
    baseline_frames: int,
    sustain_frames: int,
) -> tuple[int, np.ndarray, np.ndarray]:
    """Return the first threshold crossing sustained for a full window."""
    baseline = np.median(actions[: min(baseline_frames, len(actions))], axis=0)
    displacement = np.max(np.abs(actions - baseline), axis=1)
    moving = displacement >= threshold

    if len(moving) < sustain_frames:
        return 0, baseline, displacement

    run_counts = np.convolve(moving.astype(np.int16), np.ones(sustain_frames, dtype=np.int16), "valid")
    candidates = np.flatnonzero(run_counts == sustain_frames)
    onset = int(candidates[0]) if len(candidates) else 0
    return onset, baseline, displacement


def replace_column(table: pa.Table, name: str, values: np.ndarray) -> pa.Table:
    index = table.schema.get_field_index(name)
    if index < 0:
        raise KeyError(f"Missing expected column: {name}")
    return table.set_column(index, name, pa.array(values, type=table.schema.field(name).type))


def table_arrays(table: pa.Table) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for name in table.column_names:
        values = table[name].to_pylist()
        if not values:
            raise ValueError(f"Empty retained table for feature {name}")
        result[name] = np.stack(values) if isinstance(values[0], list) else np.asarray(values)
    return result


def hardlink_or_copy_tree(source: Path, destination: Path) -> None:
    """Copy a tree while using hard links when source and output share a filesystem."""
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(path, target)
        except OSError:
            shutil.copy2(path, target)


def copy_auxiliary_metadata(source_root: Path, output_root: Path) -> None:
    """Preserve benchmark manifests and provenance files from the source."""
    core_files = {Path("info.json"), Path("stats.json"), Path("tasks.parquet")}
    for source_file in sorted((source_root / "meta").rglob("*")):
        if not source_file.is_file():
            continue
        relative = source_file.relative_to(source_root / "meta")
        if relative in core_files or relative.parts[0] == "episodes":
            continue
        output_file = output_root / "meta" / relative
        output_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source_file, output_file)
        except OSError:
            shutil.copy2(source_file, output_file)


def validate_output(
    source_root: Path,
    output_root: Path,
    source_episodes: pd.DataFrame,
    *,
    expected_frames: int,
    fps: int,
    info: dict,
    video_keys: list[str],
    require_video_files: bool,
) -> dict:
    """Re-open the output and check its tabular, prompt, and video alignment."""
    data = pq.ParquetFile(output_root / OUTPUT_DATA_PATH)
    episodes = pd.read_parquet(output_root / OUTPUT_EPISODES_PATH)
    if data.num_row_groups != len(episodes):
        raise ValueError("Output does not have one data row group per episode")
    if data.metadata.num_rows != expected_frames:
        raise ValueError(f"Output data has {data.metadata.num_rows} rows; expected {expected_frames}")
    if episodes["length"].sum() != expected_frames:
        raise ValueError("Output episode lengths do not sum to total frames")
    if episodes["tasks"].tolist() != source_episodes["tasks"].tolist():
        raise ValueError("One or more episode prompts changed")

    expected_index = 0
    video_files: set[Path] = set()
    for episode_index, episode in episodes.iterrows():
        table = data.read_row_group(
            episode_index,
            columns=[
                "timestamp",
                "frame_index",
                "episode_index",
                "index",
                "task_index",
            ],
        )
        length = int(episode["length"])
        if len(table) != length:
            raise ValueError(f"Episode {episode_index}: row-group length mismatch")
        if table["episode_index"].to_pylist() != [episode_index] * length:
            raise ValueError(f"Episode {episode_index}: incorrect episode_index values")
        if table["frame_index"].to_pylist() != list(range(length)):
            raise ValueError(f"Episode {episode_index}: frame_index is not contiguous")
        if table["index"].to_pylist() != list(range(expected_index, expected_index + length)):
            raise ValueError(f"Episode {episode_index}: global index is not contiguous")
        timestamps = np.asarray(table["timestamp"].to_pylist(), dtype=np.float32)
        expected_timestamps = np.arange(length, dtype=np.float32) / np.float32(fps)
        if not np.allclose(timestamps, expected_timestamps, atol=1e-6):
            raise ValueError(f"Episode {episode_index}: timestamps are not frame-aligned")
        if int(episode["dataset_from_index"]) != expected_index:
            raise ValueError(f"Episode {episode_index}: incorrect dataset_from_index")
        if int(episode["dataset_to_index"]) != expected_index + length:
            raise ValueError(f"Episode {episode_index}: incorrect dataset_to_index")

        for video_key in video_keys:
            prefix = f"videos/{video_key}"
            duration = float(episode[f"{prefix}/to_timestamp"]) - float(episode[f"{prefix}/from_timestamp"])
            if round(duration * fps) != length:
                raise ValueError(f"Episode {episode_index} {video_key}: duration mismatch")
            relative_path = Path(
                info["video_path"].format(
                    video_key=video_key,
                    chunk_index=int(episode[f"{prefix}/chunk_index"]),
                    file_index=int(episode[f"{prefix}/file_index"]),
                )
            )
            video_files.add(relative_path)

        expected_index += length

    if require_video_files:
        for relative_path in video_files:
            source_file = source_root / relative_path
            output_file = output_root / relative_path
            if not source_file.is_file() or not output_file.is_file():
                raise FileNotFoundError(f"Missing source/output video pair: {relative_path}")
            if source_file.stat().st_size != output_file.stat().st_size:
                raise ValueError(f"Video size changed: {relative_path}")

    return {
        "contiguous_episode_indices": True,
        "contiguous_dataset_indices": True,
        "one_data_row_group_per_episode": True,
        "prompts_unchanged": True,
        "all_video_durations_match_retained_lengths": True,
        "byte_identical_video_file_sizes": True if require_video_files else None,
        "video_files_checked_locally": len(video_files) if require_video_files else 0,
        "video_files_expected": len(video_files),
    }


def write_card(
    output_root: Path,
    *,
    source_repo: str,
    source_revision: str,
    output_repo: str,
    summary: dict,
) -> None:
    visualizer_path = f"%2F{output_repo.replace('/', '%2F')}%2Fepisode_0"
    content = f"""---
task_categories:
- robotics
license: apache-2.0
tags:
- LeRobot
- VLA
- robotics
- compositional-generalization
- idle-prefix-trimmed
---

# VLA Reasoning Training Dataset 1200 — Trimmed Start

[Open episode 0 in the LeRobot dataset visualizer](https://huggingface.co/spaces/lerobot/visualize_dataset?path={visualizer_path})

This is a public, non-destructive derivative of
[`{source_repo}`](https://huggingface.co/datasets/{source_repo}) at revision
`{source_revision}`. It preserves all 1,200 episodes, prompts, actions, robot
states, and five camera streams, while omitting each episode's initial idle
prefix from the logical training sample.

## Transformation

- Motion is detected independently for each episode from the six-dimensional
  recorded action command.
- The baseline is the component-wise median of the first
  {summary["baseline_frames"]} frames.
- Motion onset is the first run of {summary["sustain_frames"]} consecutive
  frames whose maximum absolute joint displacement from that baseline is at
  least {summary["motion_threshold"]} motor-position units.
- {summary["pre_motion_frames"]} frames ({summary["pre_motion_seconds"]:.3f} s)
  immediately before that detected onset are retained.
- Only the initial prefix is intentionally omitted by the motion heuristic.
- {summary["alignment_tail_frames_removed"]} terminal rows across
  {summary["episodes_alignment_corrected"]} source episodes were also excluded
  to repair inherited camera/action length mismatches. This synchronization
  repair is reported separately from idle trimming in the manifest.

The camera files are byte-identical to the source files. Per-episode video
start offsets were advanced by exactly the number of omitted frames, and the
tabular rows were trimmed and reindexed to match. Thus, training and dataset
visualization expose only the retained frames without introducing video
re-encoding artifacts.

## Result

- Episodes: {summary["episodes"]:,}
- Original logical frames: {summary["original_frames"]:,}
- Retained logical frames: {summary["retained_frames"]:,}
- Omitted idle-prefix frames: {summary["idle_prefix_frames_removed"]:,}
  ({summary["idle_prefix_removed_percent"]:.2f}%)
- Source synchronization repair: {summary["alignment_tail_frames_removed"]:,}
  terminal frames across {summary["episodes_alignment_corrected"]} episodes
- Total omitted logical frames: {summary["removed_frames"]:,}
  ({summary["removed_percent"]:.2f}%)
- Episodes with a non-zero trim: {summary["episodes_trimmed"]:,}
- Frame rate: {summary["fps"]} FPS

The exact per-episode cut, detected onset, retained length, and prompt are in
`meta/trim_audit/manifest.csv`; the machine-readable configuration and checks
are in `meta/trim_audit/summary.json`. The source prompt manifests, environment
descriptions, and benchmark-design metadata are preserved under `meta/`.

## Statistics note

Action and robot-state statistics were recomputed after trimming. Visual
statistics are inherited from the source dataset because the retained images
are byte-identical and visual inputs use model-native preprocessing rather than
dataset mean/std normalization in the intended VLA-0 experiment.
"""
    (output_root / "README.md").write_text(content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()

    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output_root}")
    if not (source_root / SOURCE_DATA_PATH).is_file():
        raise FileNotFoundError(source_root / SOURCE_DATA_PATH)
    if not (source_root / SOURCE_EPISODES_PATH).is_file():
        raise FileNotFoundError(source_root / SOURCE_EPISODES_PATH)

    info = json.loads((source_root / "meta/info.json").read_text(encoding="utf-8"))
    fps = int(info["fps"])
    episodes = pd.read_parquet(source_root / SOURCE_EPISODES_PATH)
    source_episodes = episodes.copy(deep=True)
    source_data = pq.ParquetFile(source_root / SOURCE_DATA_PATH)

    if source_data.num_row_groups != len(episodes):
        raise ValueError(
            "This audited transformer expects one row group per episode: "
            f"got {source_data.num_row_groups} row groups and {len(episodes)} episodes"
        )
    if list(episodes["episode_index"]) != list(range(len(episodes))):
        raise ValueError("Episode indices are not contiguous from zero")

    output_root.mkdir(parents=True)
    (output_root / OUTPUT_DATA_PATH).parent.mkdir(parents=True)
    (output_root / OUTPUT_EPISODES_PATH).parent.mkdir(parents=True)
    (output_root / AUDIT_DIR).mkdir(parents=True)

    # Preserve the original encoded pixels exactly. Excluded frames remain in
    # the physical files but are unreachable through the revised metadata.
    if not args.overlay_only:
        hardlink_or_copy_tree(source_root / "videos", output_root / "videos")
        copy_auxiliary_metadata(source_root, output_root)
    shutil.copy2(source_root / "meta/tasks.parquet", output_root / "meta/tasks.parquet")
    if (source_root / ".gitattributes").is_file():
        shutil.copy2(source_root / ".gitattributes", output_root / ".gitattributes")

    features = info["features"]
    numeric_features = {
        key: value
        for key, value in features.items()
        if value["dtype"] not in {"image", "video", "string", "language"}
    }
    video_keys = [key for key, value in features.items() if value["dtype"] == "video"]

    output_writer = pq.ParquetWriter(
        output_root / OUTPUT_DATA_PATH,
        source_data.schema_arrow,
        compression="snappy",
        use_dictionary=True,
    )

    audit_rows: list[dict] = []
    all_episode_stats: list[dict] = []
    cumulative_index = 0

    try:
        for episode_index in range(len(episodes)):
            table = source_data.read_row_group(episode_index)
            unique_episode_indices = set(table["episode_index"].to_pylist())
            if unique_episode_indices != {episode_index}:
                raise ValueError(
                    f"Row group {episode_index} contains episode indices {unique_episode_indices}"
                )

            old_length = len(table)
            if old_length != int(episodes.at[episode_index, "length"]):
                raise ValueError(
                    f"Episode {episode_index}: data length {old_length} != metadata length "
                    f"{episodes.at[episode_index, 'length']}"
                )

            video_lengths = []
            for video_key in video_keys:
                from_key = f"videos/{video_key}/from_timestamp"
                to_key = f"videos/{video_key}/to_timestamp"
                duration = float(episodes.at[episode_index, to_key]) - float(
                    episodes.at[episode_index, from_key]
                )
                video_lengths.append(round(duration * fps))
            aligned_old_length = min(old_length, *video_lengths)
            if aligned_old_length <= 0:
                raise ValueError(f"Episode {episode_index} has no aligned camera/action frames")

            aligned_table = table.slice(0, aligned_old_length)
            actions = np.stack(aligned_table["action"].to_pylist()).astype(np.float32)
            onset, baseline, displacement = first_sustained_motion(
                actions,
                threshold=args.motion_threshold,
                baseline_frames=args.baseline_frames,
                sustain_frames=args.sustain_frames,
            )
            cut = max(0, onset - args.pre_motion_frames)
            retained = aligned_table.slice(cut)
            new_length = len(retained)
            if new_length <= 0:
                raise ValueError(f"Episode {episode_index} would be empty")

            retained = replace_column(
                retained, "timestamp", np.arange(new_length, dtype=np.float32) / np.float32(fps)
            )
            retained = replace_column(retained, "frame_index", np.arange(new_length, dtype=np.int64))
            retained = replace_column(
                retained,
                "index",
                np.arange(cumulative_index, cumulative_index + new_length, dtype=np.int64),
            )
            output_writer.write_table(retained)

            arrays = table_arrays(retained)
            episode_stats = compute_episode_stats(
                {key: arrays[key] for key in numeric_features}, numeric_features
            )
            all_episode_stats.append(episode_stats)

            episodes.at[episode_index, "length"] = new_length
            episodes.at[episode_index, "dataset_from_index"] = cumulative_index
            episodes.at[episode_index, "dataset_to_index"] = cumulative_index + new_length

            for video_key in video_keys:
                from_key = f"videos/{video_key}/from_timestamp"
                to_key = f"videos/{video_key}/to_timestamp"
                old_from = float(episodes.at[episode_index, from_key])
                old_to = float(episodes.at[episode_index, to_key])
                old_duration_frames = round((old_to - old_from) * fps)
                if old_duration_frames < aligned_old_length:
                    raise ValueError(
                        f"Episode {episode_index} {video_key}: only {old_duration_frames} video "
                        f"frames are available for aligned length {aligned_old_length}"
                    )
                new_from = old_from + cut / fps
                episodes.at[episode_index, from_key] = new_from
                new_to = old_from + aligned_old_length / fps
                episodes.at[episode_index, to_key] = new_to
                if not np.isclose(new_to - new_from, new_length / fps, atol=1e-6):
                    raise ValueError(f"Episode {episode_index} {video_key}: trimmed duration mismatch")

            for feature_name, feature_stats in episode_stats.items():
                for stat_name, stat_value in feature_stats.items():
                    column = f"stats/{feature_name}/{stat_name}"
                    if column in episodes.columns:
                        episodes.at[episode_index, column] = stat_value.tolist()

            prompt = episodes.at[episode_index, "tasks"][0]
            audit_rows.append(
                {
                    "episode_index": episode_index,
                    "prompt": prompt,
                    "task_index": int(arrays["task_index"][0]),
                    "original_length_frames": old_length,
                    "aligned_source_length_frames": aligned_old_length,
                    "source_alignment_tail_frames_removed": old_length - aligned_old_length,
                    "detected_motion_onset_frame": onset,
                    "removed_prefix_frames": cut,
                    "retained_pre_motion_frames": onset - cut,
                    "retained_length_frames": new_length,
                    "removed_prefix_seconds": cut / fps,
                    "peak_pre_onset_displacement": float(displacement[: max(onset, 1)].max()),
                    "baseline_action": json.dumps([round(float(x), 6) for x in baseline]),
                }
            )
            cumulative_index += new_length
    finally:
        output_writer.close()

    episodes.to_parquet(output_root / OUTPUT_EPISODES_PATH, index=False)

    source_stats = load_stats(source_root)
    if source_stats is None:
        raise ValueError("Source dataset has no meta/stats.json")
    aggregated_numeric = aggregate_stats(all_episode_stats)
    output_stats = dict(source_stats)
    for key in ("action", "observation.state"):
        output_stats[key] = aggregated_numeric[key]
    write_stats(output_stats, output_root)

    original_frames = int(info["total_frames"])
    removed_frames = original_frames - cumulative_index
    info["total_frames"] = cumulative_index
    (output_root / "meta/info.json").write_text(json.dumps(info, indent=4) + "\n", encoding="utf-8")

    validation = validate_output(
        source_root,
        output_root,
        source_episodes,
        expected_frames=cumulative_index,
        fps=fps,
        info=info,
        video_keys=video_keys,
        require_video_files=not args.overlay_only,
    )

    idle_prefix_frames_removed = sum(row["removed_prefix_frames"] for row in audit_rows)
    alignment_tail_frames_removed = sum(row["source_alignment_tail_frames_removed"] for row in audit_rows)
    if removed_frames != idle_prefix_frames_removed + alignment_tail_frames_removed:
        raise ValueError("Removed-frame accounting does not reconcile")
    summary = {
        "source_repo": args.source_repo,
        "source_revision": args.source_revision,
        "output_repo": args.output_repo,
        "episodes": len(episodes),
        "fps": fps,
        "original_frames": original_frames,
        "retained_frames": cumulative_index,
        "removed_frames": removed_frames,
        "removed_percent": 100.0 * removed_frames / original_frames,
        "idle_prefix_frames_removed": idle_prefix_frames_removed,
        "idle_prefix_removed_percent": 100.0 * idle_prefix_frames_removed / original_frames,
        "alignment_tail_frames_removed": alignment_tail_frames_removed,
        "episodes_alignment_corrected": sum(
            row["source_alignment_tail_frames_removed"] > 0 for row in audit_rows
        ),
        "episodes_trimmed": sum(row["removed_prefix_frames"] > 0 for row in audit_rows),
        "motion_threshold": args.motion_threshold,
        "baseline_frames": args.baseline_frames,
        "sustain_frames": args.sustain_frames,
        "pre_motion_frames": args.pre_motion_frames,
        "pre_motion_seconds": args.pre_motion_frames / fps,
        "video_handling": "byte-identical source files; per-episode from_timestamp shifted",
        "assembly_mode": "server-side duplicate metadata overlay"
        if args.overlay_only
        else "complete local derivative",
        "tail_trimming": "only inherited source camera/action length reconciliation",
        "validation": validation,
    }

    manifest_path = output_root / AUDIT_DIR / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)
    (output_root / AUDIT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    write_card(
        output_root,
        source_repo=args.source_repo,
        source_revision=args.source_revision,
        output_repo=args.output_repo,
        summary=summary,
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
