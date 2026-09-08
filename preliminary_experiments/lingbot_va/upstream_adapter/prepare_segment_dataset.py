#!/usr/bin/env python
"""Build a LingBot-VA-native latent/action segment cache from a LeRobot v3 dataset.

The source dataset is opened read-only. The output is a derived cache consumed by
``upstream/segment_dataset.py``; it contains no copied source videos.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as nnf
from tqdm import tqdm

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.video_utils import decode_video_frames
from lerobot.policies.lingbot_va.utils import (
    WanVAEStreamingWrapper,
    clean_prompt,
    load_text_encoder,
    load_tokenizer,
    load_vae,
)

FORMAT_VERSION = 1
TEMPORAL_DOWNSAMPLE = 4
ACTION_DIM = 30
ACTION_PER_LATENT_FRAME = 8
DEFAULT_ACTION_CHANNELS = (0, 1, 2, 3, 4, 28)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo-id", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--model-path",
        required=True,
        help="HF repo id or local directory containing vae/, text_encoder/, and tokenizer/.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Optional local source-dataset root. Omit to use HF_LEROBOT_HOME/the Hub cache.",
    )
    parser.add_argument(
        "--camera-keys",
        nargs="+",
        default=["observation.images.middle", "observation.images.wrist"],
        help="Camera keys in the exact left-to-right latent concatenation order.",
    )
    parser.add_argument("--target-fps", type=int, default=15)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument(
        "--max-segment-seconds",
        type=float,
        default=0.0,
        help="0 makes one full-length segment per episode; otherwise creates consecutive segments.",
    )
    parser.add_argument("--validation-fraction", type=float, default=0.0)
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--video-backend", choices=["pyav", "torchcodec"], default="pyav")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    parser.add_argument("--text-encoder-device", default="cuda:0")
    parser.add_argument("--vae-chunk-frames", type=int, default=16)
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Write/validate the manifest and print its training math without loading Wan models.",
    )
    return parser.parse_args()


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    tmp.replace(path)


def _jsonl_dump(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as stream:
        for value in values:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
    tmp.replace(path)


def _torch_save_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    torch.save(value, tmp)
    tmp.replace(path)


def _dtype(name: str) -> torch.dtype:
    return {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[name]


def _task_id(task: str) -> str:
    return hashlib.sha256(task.encode("utf-8")).hexdigest()[:20]


def _episode_splits(num_episodes: int, validation_fraction: float, seed: int) -> dict[int, str]:
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("--validation-fraction must be in [0, 1).")
    indices = list(range(num_episodes))
    random.Random(seed).shuffle(indices)
    validation_count = round(num_episodes * validation_fraction)
    validation = set(indices[:validation_count])
    return {
        episode_index: ("validation" if episode_index in validation else "train") for episode_index in indices
    }


def _aligned_segment_ranges(length: int, max_segment_frames: int | None) -> list[tuple[int, int]]:
    """Return half-open frame ranges aligned to one LingBot latent/action unit (8 source frames)."""
    aligned_length = length - length % ACTION_PER_LATENT_FRAME
    if aligned_length < ACTION_PER_LATENT_FRAME:
        return []
    if max_segment_frames is None:
        return [(0, aligned_length)]
    max_segment_frames -= max_segment_frames % ACTION_PER_LATENT_FRAME
    if max_segment_frames < ACTION_PER_LATENT_FRAME:
        raise ValueError("--max-segment-seconds is too short after alignment to 8 source frames.")
    ranges = []
    start = 0
    while start < aligned_length:
        end = min(start + max_segment_frames, aligned_length)
        if end - start >= ACTION_PER_LATENT_FRAME:
            ranges.append((start, end))
        start = end
    return ranges


def _episode_task(episode: dict[str, Any]) -> str:
    tasks = episode.get("tasks")
    if isinstance(tasks, str):
        return tasks
    if tasks:
        return str(tasks[0])
    raise ValueError(f"Episode {episode.get('episode_index')} has no task description.")


def _make_plan(
    dataset: LeRobotDataset, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_fps = int(dataset.fps)
    if source_fps % args.target_fps != 0:
        raise ValueError(
            f"Source FPS {source_fps} must be evenly divisible by target FPS {args.target_fps}; "
            "the native recipe needs a fixed integer frame stride."
        )
    stride = source_fps // args.target_fps
    expected_stride = ACTION_PER_LATENT_FRAME // TEMPORAL_DOWNSAMPLE
    if stride != expected_stride:
        raise ValueError(
            f"This 8-actions-per-latent recipe requires video stride {expected_stride}, got {stride}. "
            f"For a {source_fps} FPS dataset, use --target-fps {source_fps // expected_stride}."
        )

    episode_count = dataset.meta.total_episodes
    if args.max_episodes is not None:
        episode_count = min(episode_count, args.max_episodes)
    split_by_episode = _episode_splits(episode_count, args.validation_fraction, args.split_seed)

    max_segment_frames = None
    if args.max_segment_seconds > 0:
        max_segment_frames = math.floor(args.max_segment_seconds * source_fps)

    manifest: list[dict[str, Any]] = []
    episodes_out: list[dict[str, Any]] = []
    for episode_index in range(episode_count):
        episode = dataset.meta.episodes[episode_index]
        length = int(episode["dataset_to_index"] - episode["dataset_from_index"])
        ranges = _aligned_segment_ranges(length, max_segment_frames)
        action_config = []
        task = _episode_task(episode)
        task_id = _task_id(task)
        for segment_index, (start_frame, end_frame) in enumerate(ranges):
            segment_id = f"episode_{episode_index:06d}_{start_frame:06d}_{end_frame:06d}"
            record = {
                "format_version": FORMAT_VERSION,
                "segment_id": segment_id,
                "episode_index": episode_index,
                "segment_index": segment_index,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "source_frame_count": end_frame - start_frame,
                "target_video_frame_count": (end_frame - start_frame) // stride,
                "latent_frame_count": (end_frame - start_frame) // ACTION_PER_LATENT_FRAME,
                "task": task,
                "task_id": task_id,
                "text_embedding": f"text_embeddings/{task_id}.pt",
                "data": f"segments/{segment_id}.pt",
                "split": split_by_episode[episode_index],
            }
            manifest.append(record)
            action_config.append({"start_frame": start_frame, "end_frame": end_frame})
        episodes_out.append(
            {
                "episode_index": episode_index,
                "tasks": [task],
                "action_config": action_config,
                "split": split_by_episode[episode_index],
            }
        )
    if not manifest:
        raise ValueError("No valid segments were produced.")
    return manifest, episodes_out


def _action_quantiles(
    dataset: LeRobotDataset, manifest: list[dict[str, Any]]
) -> tuple[np.ndarray, np.ndarray]:
    view = dataset.hf_dataset.with_format(type="numpy", columns=["action"], output_all_columns=False)
    episode_ids = sorted({int(record["episode_index"]) for record in manifest})
    chunks = []
    for episode_index in tqdm(episode_ids, desc="Reading actions for q01/q99"):
        episode = dataset.meta.episodes[episode_index]
        start = int(episode["dataset_from_index"])
        end = int(episode["dataset_to_index"])
        values = np.asarray(view[start:end]["action"], dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != len(DEFAULT_ACTION_CHANNELS):
            raise ValueError(
                f"Episode {episode_index} action shape is {values.shape}; expected [frames, 6] "
                f"for channels {list(DEFAULT_ACTION_CHANNELS)}."
            )
        chunks.append(values)
    actions = np.concatenate(chunks, axis=0)
    return np.quantile(actions, 0.01, axis=0), np.quantile(actions, 0.99, axis=0)


def _encode_text(
    text_encoder, tokenizer, text: str, device: torch.device, dtype: torch.dtype
) -> torch.Tensor:
    prompt = clean_prompt(text)
    tokens = tokenizer(
        [prompt],
        padding="max_length",
        max_length=512,
        truncation=True,
        add_special_tokens=True,
        return_attention_mask=True,
        return_tensors="pt",
    )
    input_ids = tokens.input_ids.to(device)
    mask = tokens.attention_mask.to(device)
    with torch.inference_mode():
        embeds = text_encoder(input_ids, mask).last_hidden_state
    sequence_length = int(mask.gt(0).sum().item())
    embeds = embeds[:, :sequence_length]
    embeds = torch.cat([embeds, embeds.new_zeros(1, 512 - sequence_length, embeds.shape[-1])], dim=1)
    return embeds.squeeze(0).to(dtype=dtype, device="cpu").contiguous()


def _precompute_text_embeddings(args: argparse.Namespace, manifest: list[dict[str, Any]]) -> None:
    task_by_id = {record["task_id"]: record["task"] for record in manifest}
    output_paths = {task_id: args.output_root / "text_embeddings" / f"{task_id}.pt" for task_id in task_by_id}
    empty_path = args.output_root / "empty_emb.pt"
    missing = [task_id for task_id, path in output_paths.items() if not path.is_file()]
    if not missing and empty_path.is_file():
        print(f"Text embeddings already complete ({len(task_by_id)} tasks).")
        return

    dtype = _dtype(args.dtype)
    device = torch.device(args.text_encoder_device)
    tokenizer = load_tokenizer(args.model_path, subfolder="tokenizer")
    text_encoder = load_text_encoder(args.model_path, dtype, device, subfolder="text_encoder").eval()
    for task_id in tqdm(missing, desc="Encoding UMT5 task prompts"):
        embedding = _encode_text(text_encoder, tokenizer, task_by_id[task_id], device, dtype)
        _torch_save_atomic(output_paths[task_id], embedding)
    if not empty_path.is_file():
        _torch_save_atomic(empty_path, _encode_text(text_encoder, tokenizer, "", device, dtype))
    del text_encoder, tokenizer
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()


def _decode_segment_camera(
    dataset: LeRobotDataset,
    record: dict[str, Any],
    camera_key: str,
    target_stride: int,
    backend: str,
) -> torch.Tensor:
    episode_index = int(record["episode_index"])
    episode = dataset.meta.episodes[episode_index]
    global_start = int(episode["dataset_from_index"]) + int(record["start_frame"])
    global_end = int(episode["dataset_from_index"]) + int(record["end_frame"])
    sampled_indices = list(range(global_start, global_end, target_stride))
    timestamp_view = dataset.hf_dataset.with_format(
        type="numpy", columns=["timestamp"], output_all_columns=False
    )
    local_timestamps = np.asarray(timestamp_view[sampled_indices]["timestamp"], dtype=np.float64).tolist()
    from_timestamp = float(episode[f"videos/{camera_key}/from_timestamp"])
    shifted_timestamps = [from_timestamp + timestamp for timestamp in local_timestamps]
    video_path = dataset.root / dataset.meta.get_video_file_path(episode_index, camera_key)
    return decode_video_frames(
        video_path,
        shifted_timestamps,
        tolerance_s=max(dataset.tolerance_s, 0.51 / dataset.fps),
        backend=backend,
        return_uint8=True,
    )


def _encode_camera_latents(
    frames: torch.Tensor,
    streaming_vae: WanVAEStreamingWrapper,
    vae,
    device: torch.device,
    dtype: torch.dtype,
    size: tuple[int, int],
    chunk_frames: int,
) -> torch.Tensor:
    streaming_vae.clear_cache()
    mean = torch.tensor(vae.config.latents_mean, device=device).view(1, -1, 1, 1, 1)
    inv_std = (1.0 / torch.tensor(vae.config.latents_std, device=device)).view(1, -1, 1, 1, 1)
    encoded = []
    for start in range(0, frames.shape[0], chunk_frames):
        chunk = frames[start : start + chunk_frames].to(device=device, dtype=torch.float32)
        chunk = nnf.interpolate(chunk, size=size, mode="bilinear", align_corners=False)
        chunk = (chunk.div_(127.5).sub_(1.0)).permute(1, 0, 2, 3).unsqueeze(0).to(dtype)
        with torch.inference_mode():
            enc = streaming_vae.encode_chunk(chunk)
            mu, _ = torch.chunk(enc, 2, dim=1)
            normalized = ((mu.float() - mean) * inv_std).to(dtype)
        encoded.append(normalized.cpu())
        del chunk, enc, mu, normalized
    return torch.cat(encoded, dim=2).squeeze(0).contiguous()


def _segment_actions(
    dataset: LeRobotDataset,
    record: dict[str, Any],
    q01: np.ndarray,
    q99: np.ndarray,
) -> tuple[torch.Tensor, torch.Tensor]:
    episode = dataset.meta.episodes[int(record["episode_index"])]
    global_start = int(episode["dataset_from_index"]) + int(record["start_frame"])
    global_end = int(episode["dataset_from_index"]) + int(record["end_frame"])
    view = dataset.hf_dataset.with_format(type="numpy", columns=["action"], output_all_columns=False)
    compact = np.asarray(view[global_start:global_end]["action"], dtype=np.float32)

    # Match upstream _action_post_process: a zero action block precedes the source actions.
    shifted = np.pad(compact, ((ACTION_PER_LATENT_FRAME, 0), (0, 0)), constant_values=0)
    required = int(record["latent_frame_count"]) * ACTION_PER_LATENT_FRAME
    compact = shifted[:required]
    if compact.shape != (required, len(DEFAULT_ACTION_CHANNELS)):
        raise ValueError(f"Unexpected aligned action shape {compact.shape} for {record['segment_id']}.")

    full = np.zeros((required, ACTION_DIM), dtype=np.float32)
    mask = np.zeros((required, ACTION_DIM), dtype=bool)
    for source_column, channel_id in enumerate(DEFAULT_ACTION_CHANNELS):
        normalized = (compact[:, source_column] - q01[source_column]) / (
            q99[source_column] - q01[source_column] + 1e-6
        )
        full[:, channel_id] = np.clip(normalized * 2.0 - 1.0, -1.5, 1.5)
        mask[:, channel_id] = True
    full *= mask
    latent_frames = int(record["latent_frame_count"])
    actions = torch.from_numpy(full.reshape(latent_frames, ACTION_PER_LATENT_FRAME, ACTION_DIM))
    actions = actions.permute(2, 0, 1).unsqueeze(-1).contiguous()
    actions_mask = torch.from_numpy(mask.reshape(latent_frames, ACTION_PER_LATENT_FRAME, ACTION_DIM))
    actions_mask = actions_mask.permute(2, 0, 1).unsqueeze(-1).contiguous()
    return actions, actions_mask


def _precompute_segments(
    dataset: LeRobotDataset,
    args: argparse.Namespace,
    manifest: list[dict[str, Any]],
    q01: np.ndarray,
    q99: np.ndarray,
) -> None:
    missing = [record for record in manifest if not (args.output_root / record["data"]).is_file()]
    if not missing:
        print(f"Segment cache already complete ({len(manifest)} segments).")
        return
    dtype = _dtype(args.dtype)
    device = torch.device(args.device)
    vae = load_vae(args.model_path, dtype, device, subfolder="vae").eval()
    streaming_vae = WanVAEStreamingWrapper(vae)
    target_stride = dataset.fps // args.target_fps

    for record in tqdm(missing, desc="Encoding Wan VAE segment latents"):
        started = time.monotonic()
        camera_latents = []
        for camera_key in args.camera_keys:
            frames = _decode_segment_camera(dataset, record, camera_key, target_stride, args.video_backend)
            latents = _encode_camera_latents(
                frames,
                streaming_vae,
                vae,
                device,
                dtype,
                (args.height, args.width),
                args.vae_chunk_frames,
            )
            camera_latents.append(latents)
            del frames, latents
        latents = torch.cat(camera_latents, dim=-1)
        expected_frames = int(record["latent_frame_count"])
        if latents.shape[1] != expected_frames:
            raise ValueError(
                f"Wan VAE produced {latents.shape[1]} latent frames for {record['segment_id']}; "
                f"expected {expected_frames}. Use --vae-chunk-frames divisible by 4."
            )
        actions, actions_mask = _segment_actions(dataset, record, q01, q99)
        value = {
            "format_version": FORMAT_VERSION,
            "latents": latents,
            # Upstream's native loader returns action targets as float32.
            "actions": actions,
            "actions_mask": actions_mask,
            "episode_index": int(record["episode_index"]),
            "start_frame": int(record["start_frame"]),
            "end_frame": int(record["end_frame"]),
            "camera_keys": list(args.camera_keys),
        }
        _torch_save_atomic(args.output_root / record["data"], value)
        record["preprocess_seconds"] = round(time.monotonic() - started, 3)
        del camera_latents, latents, actions, actions_mask, value
        torch.cuda.empty_cache()
    del streaming_vae, vae
    gc.collect()
    torch.cuda.empty_cache()


def _validate_cache(root: Path, manifest: list[dict[str, Any]], require_data: bool) -> None:
    failures = []
    for record in manifest:
        text_path = root / record["text_embedding"]
        data_path = root / record["data"]
        if require_data and not text_path.is_file():
            failures.append(str(text_path))
        if require_data and not data_path.is_file():
            failures.append(str(data_path))
    if require_data and not (root / "empty_emb.pt").is_file():
        failures.append(str(root / "empty_emb.pt"))
    if failures:
        preview = "\n".join(failures[:10])
        raise FileNotFoundError(f"Derived cache is incomplete ({len(failures)} missing files):\n{preview}")


def main() -> None:
    args = parse_args()
    if args.vae_chunk_frames <= 0 or args.vae_chunk_frames % TEMPORAL_DOWNSAMPLE != 0:
        raise ValueError("--vae-chunk-frames must be a positive multiple of 4.")
    if args.height % 16 or args.width % 16:
        raise ValueError("--height and --width must be divisible by 16.")
    for camera_key in args.camera_keys:
        if not camera_key.startswith("observation.images."):
            raise ValueError(f"Expected an observation.images.* camera key, got {camera_key!r}.")

    args.output_root = args.output_root.resolve()
    args.output_root.mkdir(parents=True, exist_ok=True)
    dataset = LeRobotDataset(
        repo_id=args.source_repo_id,
        root=args.source_root,
        revision=args.source_revision,
        download_videos=not args.plan_only,
        video_backend=args.video_backend,
        return_uint8=True,
    )
    missing_cameras = set(args.camera_keys) - set(dataset.meta.video_keys)
    if missing_cameras:
        raise ValueError(f"Camera keys not present in source dataset: {sorted(missing_cameras)}")

    manifest, episode_metadata = _make_plan(dataset, args)
    q01, q99 = _action_quantiles(dataset, manifest)
    split_counts: dict[str, int] = defaultdict(int)
    for record in manifest:
        split_counts[record["split"]] += 1

    recipe = {
        "format_version": FORMAT_VERSION,
        "source": {
            "repo_id": args.source_repo_id,
            "revision": args.source_revision,
            "resolved_root": str(dataset.root),
            "fps": dataset.fps,
            "total_episodes": dataset.meta.total_episodes,
        },
        "derived": {
            "camera_keys": list(args.camera_keys),
            "target_fps": args.target_fps,
            "height": args.height,
            "width": args.width,
            "temporal_downsample": TEMPORAL_DOWNSAMPLE,
            "action_per_frame": ACTION_PER_LATENT_FRAME,
            "action_dim": ACTION_DIM,
            "used_action_channel_ids": list(DEFAULT_ACTION_CHANNELS),
            "max_segment_seconds": args.max_segment_seconds,
            "validation_fraction": args.validation_fraction,
            "split_seed": args.split_seed,
            "segment_count": len(manifest),
            "split_counts": dict(split_counts),
        },
        "normalization": {"method": "quantiles", "q01_compact": q01.tolist(), "q99_compact": q99.tolist()},
        "model_path": args.model_path,
    }
    existing_recipe_path = args.output_root / "dataset_info.json"
    if existing_recipe_path.is_file():
        existing = json.loads(existing_recipe_path.read_text(encoding="utf-8"))
        comparable_keys = ("source", "derived", "normalization", "model_path")
        if any(existing.get(key) != recipe.get(key) for key in comparable_keys):
            raise RuntimeError(
                f"{existing_recipe_path} describes a different recipe. Choose a new --output-root; "
                "the converter will not overwrite an incompatible derived cache."
            )
    _json_dump(existing_recipe_path, recipe)
    _jsonl_dump(args.output_root / "episodes.jsonl", episode_metadata)
    _jsonl_dump(args.output_root / "manifest.jsonl", manifest)

    train_segments = split_counts.get("train", 0)
    steps_per_epoch = math.ceil(train_segments / 32)
    print(
        f"Planned {len(manifest)} segments ({train_segments} train, "
        f"{split_counts.get('validation', 0)} validation)."
    )
    print(
        f"At global batch 32: {steps_per_epoch} optimizer steps/epoch, {12 * steps_per_epoch} steps/12 epochs."
    )
    if args.plan_only:
        print("Plan-only mode: models were not loaded and latent/embedding files were not generated.")
        return

    _precompute_text_embeddings(args, manifest)
    _precompute_segments(dataset, args, manifest, q01, q99)
    _jsonl_dump(args.output_root / "manifest.jsonl", manifest)
    _validate_cache(args.output_root, manifest, require_data=True)
    _json_dump(
        args.output_root / "READY.json",
        {
            "format_version": FORMAT_VERSION,
            "segments": len(manifest),
            "train_segments": train_segments,
            "validation_segments": split_counts.get("validation", 0),
            "completed_at_unix": time.time(),
        },
    )
    print(f"Derived LingBot-VA cache is ready: {args.output_root}")


if __name__ == "__main__":
    main()
