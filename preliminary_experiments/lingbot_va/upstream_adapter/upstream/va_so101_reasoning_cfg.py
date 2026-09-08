"""SO-101 configuration for the derived 256x256, 15 FPS segment cache."""

import json
import os
from pathlib import Path

from easydict import EasyDict

from .shared_config import va_shared_cfg

dataset_root = Path(os.environ["LINGBOT_DATASET_PATH"])
dataset_info = json.loads((dataset_root / "dataset_info.json").read_text(encoding="utf-8"))
compact_q01 = dataset_info["normalization"]["q01_compact"]
compact_q99 = dataset_info["normalization"]["q99_compact"]
used_channels = [0, 1, 2, 3, 4, 28]

q01 = [0.0] * 30
q99 = [0.0] * 30
for source_column, channel_id in enumerate(used_channels):
    q01[channel_id] = compact_q01[source_column]
    q99[channel_id] = compact_q99[source_column]

va_so101_reasoning_cfg = EasyDict(__name__="Config: SO-101 reasoning")
va_so101_reasoning_cfg.update(va_shared_cfg)
va_so101_reasoning_cfg.infer_mode = "server"
va_so101_reasoning_cfg.wan22_pretrained_model_name_or_path = os.environ["LINGBOT_BASE_MODEL_PATH"]
va_so101_reasoning_cfg.attn_window = 30
va_so101_reasoning_cfg.frame_chunk_size = 4
va_so101_reasoning_cfg.env_type = "none"
va_so101_reasoning_cfg.height = 256
va_so101_reasoning_cfg.width = 256
va_so101_reasoning_cfg.action_dim = 30
va_so101_reasoning_cfg.action_per_frame = 8
va_so101_reasoning_cfg.obs_cam_keys = dataset_info["derived"]["camera_keys"]
va_so101_reasoning_cfg.guidance_scale = 5
va_so101_reasoning_cfg.action_guidance_scale = 1
va_so101_reasoning_cfg.num_inference_steps = 5
va_so101_reasoning_cfg.video_exec_step = -1
va_so101_reasoning_cfg.action_num_inference_steps = 10
va_so101_reasoning_cfg.snr_shift = 5.0
va_so101_reasoning_cfg.action_snr_shift = 1.0
va_so101_reasoning_cfg.used_action_channel_ids = used_channels
va_so101_reasoning_cfg.inverse_used_action_channel_ids = [len(used_channels)] * 30
for source_column, channel_id in enumerate(used_channels):
    va_so101_reasoning_cfg.inverse_used_action_channel_ids[channel_id] = source_column
va_so101_reasoning_cfg.action_norm_method = "quantiles"
va_so101_reasoning_cfg.norm_stat = {"q01": q01, "q99": q99}
