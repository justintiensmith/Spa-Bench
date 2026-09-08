"""Environment-driven upstream training configuration for the SO-101 cache."""

import os

from easydict import EasyDict

from .va_so101_reasoning_cfg import va_so101_reasoning_cfg


def _bool_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


va_so101_reasoning_train_cfg = EasyDict(__name__="Config: SO-101 reasoning train")
va_so101_reasoning_train_cfg.update(va_so101_reasoning_cfg)
va_so101_reasoning_train_cfg.dataset_path = os.environ["LINGBOT_DATASET_PATH"]
va_so101_reasoning_train_cfg.empty_emb_path = os.path.join(
    va_so101_reasoning_train_cfg.dataset_path, "empty_emb.pt"
)
va_so101_reasoning_train_cfg.enable_wandb = _bool_env("LINGBOT_ENABLE_WANDB")
va_so101_reasoning_train_cfg.load_worker = int(os.getenv("LINGBOT_LOAD_WORKERS", "4"))
va_so101_reasoning_train_cfg.save_interval = int(os.environ["LINGBOT_SAVE_INTERVAL"])
va_so101_reasoning_train_cfg.eval_interval = int(
    os.getenv("LINGBOT_EVAL_INTERVAL", os.environ["LINGBOT_SAVE_INTERVAL"])
)
va_so101_reasoning_train_cfg.eval_batches = int(os.getenv("LINGBOT_EVAL_BATCHES", "16"))
va_so101_reasoning_train_cfg.gc_interval = int(os.getenv("LINGBOT_GC_INTERVAL", "25"))
va_so101_reasoning_train_cfg.cfg_prob = float(os.getenv("LINGBOT_CFG_PROB", "0.1"))
va_so101_reasoning_train_cfg.learning_rate = float(os.getenv("LINGBOT_LR", "1e-4"))
va_so101_reasoning_train_cfg.beta1 = 0.9
va_so101_reasoning_train_cfg.beta2 = 0.95
va_so101_reasoning_train_cfg.weight_decay = 1e-1
va_so101_reasoning_train_cfg.warmup_steps = int(os.getenv("LINGBOT_WARMUP_STEPS", "10"))
va_so101_reasoning_train_cfg.batch_size = 1
va_so101_reasoning_train_cfg.gradient_accumulation_steps = 8
va_so101_reasoning_train_cfg.num_steps = int(os.environ["LINGBOT_NUM_STEPS"])
