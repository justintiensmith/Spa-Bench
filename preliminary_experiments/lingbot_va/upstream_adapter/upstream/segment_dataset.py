"""Dataset adapter for caches made by prepare_segment_dataset.py.

This file is installed into the pinned upstream LingBot-VA checkout as
``wan_va/dataset/segment_dataset.py``.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import torch


class MultiLatentLeRobotDataset(torch.utils.data.Dataset):
    """Read one precomputed segment per item without importing legacy LeRobot v2.1."""

    def __init__(self, config, split: str = "train"):
        self.root = Path(config.dataset_path)
        self.split = split
        self.cfg_prob = float(config.cfg_prob) if split == "train" else 0.0
        manifest_path = self.root / "manifest.jsonl"
        ready_path = self.root / "READY.json"
        if not ready_path.is_file():
            raise FileNotFoundError(
                f"Derived cache is not marked ready: {ready_path}. Finish prepare_segment_dataset.py first."
            )
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        with manifest_path.open("r", encoding="utf-8") as stream:
            records = [json.loads(line) for line in stream if line.strip()]
        self.records = [record for record in records if record.get("split", "train") == split]
        if not self.records and split == "train":
            raise ValueError(f"No {split!r} records in {manifest_path}.")
        self.empty_emb = torch.load(self.root / "empty_emb.pt", map_location="cpu", weights_only=True)
        self._text_cache = {}

    def __len__(self):
        return len(self.records)

    def _load_text_embedding(self, relative_path: str):
        if relative_path not in self._text_cache:
            if len(self._text_cache) >= 16:
                self._text_cache.pop(next(iter(self._text_cache)))
            self._text_cache[relative_path] = torch.load(
                self.root / relative_path, map_location="cpu", weights_only=True
            )
        return self._text_cache[relative_path]

    def __getitem__(self, index):
        record = self.records[index % len(self.records)]
        value = torch.load(self.root / record["data"], map_location="cpu", weights_only=True)
        latents = value["latents"]
        actions = value["actions"]
        actions_mask = value["actions_mask"]
        if latents.ndim != 4 or latents.shape[0] != 48:
            raise ValueError(f"Invalid latent shape {tuple(latents.shape)} in {record['data']}.")
        expected_action_shape = (30, latents.shape[1], 8, 1)
        if tuple(actions.shape) != expected_action_shape:
            raise ValueError(
                f"Invalid action shape {tuple(actions.shape)} in {record['data']}; "
                f"expected {expected_action_shape}."
            )
        text_emb = (
            self.empty_emb
            if self.cfg_prob > 0.0 and random.random() < self.cfg_prob
            else self._load_text_embedding(record["text_embedding"])
        )
        return {
            "latents": latents,
            "text_emb": text_emb,
            "actions": actions,
            "actions_mask": actions_mask,
        }


__all__ = ["MultiLatentLeRobotDataset"]
