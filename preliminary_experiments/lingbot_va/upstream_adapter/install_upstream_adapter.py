#!/usr/bin/env python
"""Install the v3 segment-cache adapter into a pinned LingBot-VA checkout."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

EXPECTED_COMMIT = "7c6ffa9bfc4b83582cafc860fab4c82cc7deeeeb"
MARKER = "# LINGBOT_SO101_SEGMENT_ADAPTER_V1"


def _replace_once(text: str, old: str, new: str, path: Path) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one patch anchor in {path}, found {count}: {old[:80]!r}")
    return text.replace(old, new, 1)


def _patch_dataset_init(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    text = _replace_once(
        text,
        "from .lerobot_latent_dataset import MultiLatentLeRobotDataset",
        f"{MARKER}\nfrom .segment_dataset import MultiLatentLeRobotDataset",
        path,
    )
    path.write_text(text, encoding="utf-8")


def _patch_configs_init(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    text = _replace_once(
        text,
        "from .va_libero_i2va import va_libero_i2va_cfg\n",
        "from .va_libero_i2va import va_libero_i2va_cfg\n"
        f"{MARKER}\n"
        "from .va_so101_reasoning_train_cfg import va_so101_reasoning_train_cfg\n",
        path,
    )
    text = _replace_once(
        text,
        "    'libero_i2av': va_libero_i2va_cfg,\n}",
        "    'libero_i2av': va_libero_i2va_cfg,\n"
        "    'so101_reasoning_train': va_so101_reasoning_train_cfg,\n}",
        path,
    )
    path.write_text(text, encoding="utf-8")


def _patch_train(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    text = _replace_once(
        text,
        """            wandb.login(host=os.environ['WANDB_BASE_URL'], key=os.environ['WANDB_API_KEY'])
            self.wandb = wandb
            self.wandb.init(
                entity=os.environ["WANDB_TEAM_NAME"],
                project=os.getenv("WANDB_PROJECT", "va_robotwin"),
                # dir=log_dir,
                config=config,
                mode="online",
                name='test_lln'
                # name=os.path.basename(os.path.normpath(job_config.job.dump_folder))
            )
""",
        """            wandb.login(host=os.getenv('WANDB_BASE_URL', 'https://api.wandb.ai'),
                        key=os.environ['WANDB_API_KEY'])
            self.wandb = wandb
            self.wandb.init(
                entity=os.getenv("WANDB_TEAM_NAME") or None,
                project=os.getenv("WANDB_PROJECT", "VLA_Reasoning"),
                config=config,
                mode="online",
                name=os.getenv("LINGBOT_RUN_NAME", "lingbot_so101_reasoning")
            )
""",
        path,
    )
    text = _replace_once(
        text,
        "        train_dataset = MultiLatentLeRobotDataset(config=config)\n",
        f"        {MARKER}\n        train_dataset = MultiLatentLeRobotDataset(config=config, split='train')\n",
        path,
    )
    loader_anchor = (
        "        self.train_loader = DataLoader(\n"
        "            train_dataset,\n"
        "            batch_size=config.batch_size,\n"
        "            shuffle=(train_sampler is None), "
        "\n"
        "            num_workers=config.load_worker,\n"
        "            sampler=train_sampler,\n"
        "        )\n"
        "\n"
        "        self.train_scheduler_latent"
    )
    loader_replacement = """        self.train_loader = DataLoader(
            train_dataset,
            batch_size=config.batch_size,
            shuffle=(train_sampler is None),
            num_workers=config.load_worker,
            sampler=train_sampler,
        )

        self.eval_loader = None
        if getattr(config, 'eval_interval', 0) > 0:
            eval_dataset = MultiLatentLeRobotDataset(config=config, split='validation')
            if len(eval_dataset) > 0:
                eval_sampler = DistributedSampler(
                    eval_dataset,
                    num_replicas=config.world_size,
                    rank=config.rank,
                    shuffle=False,
                ) if config.world_size > 1 else None
                self.eval_loader = DataLoader(
                    eval_dataset,
                    batch_size=1,
                    shuffle=False,
                    num_workers=min(config.load_worker, 4),
                    sampler=eval_sampler,
                )
                if config.rank == 0:
                    logger.info(f"Validation enabled with {len(eval_dataset)} segments")
            elif config.rank == 0:
                logger.warning("No validation segments found; checkpoint evaluation is disabled")

        self.train_scheduler_latent"""
    text = _replace_once(text, loader_anchor, loader_replacement, path)

    evaluate_method = r'''    @torch.no_grad()
    def evaluate(self):
        """Compute distributed validation losses on a bounded segment sample."""
        if self.eval_loader is None:
            return None
        self.transformer.eval()
        totals = torch.zeros(3, dtype=torch.float64, device=self.device)
        max_batches = getattr(self.config, 'eval_batches', 16)
        for batch_idx, batch in enumerate(self.eval_loader):
            if batch_idx >= max_batches:
                break
            # Stable noise/chunk sampling makes checkpoint-to-checkpoint comparisons useful.
            torch.manual_seed(1729 + batch_idx)
            batch = self.convert_input_format(batch)
            input_dict = self._prepare_input_dict(batch)
            output = self.transformer(input_dict, train_mode=True)
            latent_loss, action_loss = self.compute_loss(input_dict, output)
            scale = self.gradient_accumulation_steps
            totals[0] += latent_loss.detach().double() * scale
            totals[1] += action_loss.detach().double() * scale
            totals[2] += 1
        if dist.is_initialized():
            dist.all_reduce(totals, op=dist.ReduceOp.SUM)
        denom = totals[2].clamp_min(1)
        metrics = {
            'eval/video_loss': (totals[0] / denom).item(),
            'eval/action_loss': (totals[1] / denom).item(),
            'eval/segments': int(totals[2].item()),
        }
        self.transformer.train()
        if self.config.rank == 0:
            logger.info(
                f"Validation at step {self.step}: video_loss={metrics['eval/video_loss']:.6f}, "
                f"action_loss={metrics['eval/action_loss']:.6f}, segments={metrics['eval/segments']}"
            )
            if self.config.enable_wandb:
                self.wandb.log(metrics, step=self.step)
        return metrics

'''
    text = _replace_once(
        text, "    def save_checkpoint(self,):\n", evaluate_method + "    def save_checkpoint(self,):\n", path
    )
    checkpoint_anchor = """                if self.step % self.config.save_interval == 0:
                    if self.config.rank == 0:
                        logger.info(f"Starting save model at step {self.step}")
                    self.save_checkpoint()

            if dist.is_initialized():"""
    checkpoint_replacement = """                if self.step % self.config.save_interval == 0:
                    if self.config.rank == 0:
                        logger.info(f"Starting save model at step {self.step}")
                    self.save_checkpoint()

                if self.eval_loader is not None and self.step % self.config.eval_interval == 0:
                    self.evaluate()

            if dist.is_initialized():"""
    text = _replace_once(text, checkpoint_anchor, checkpoint_replacement, path)
    path.write_text(text, encoding="utf-8")


def _patch_optional_flash_attention(path: Path) -> None:
    """The FSDP recipe uses FlexAttention, so FlashAttention must not be an import-time dependency."""
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    old = """try:
    from flash_attn_interface import flash_attn_func
except:
    from flash_attn import flash_attn_func
"""
    new = f"""{MARKER}
try:
    from flash_attn_interface import flash_attn_func
except ImportError:
    try:
        from flash_attn import flash_attn_func
    except ImportError:
        flash_attn_func = None
"""
    text = _replace_once(text, old, new, path)
    text = _replace_once(
        text,
        """        elif attn_mode == 'flashattn':
            self.attn_op = flash_attn_func
""",
        """        elif attn_mode == 'flashattn':
            if flash_attn_func is None:
                raise ImportError("attn_mode='flashattn' requires flash-attn; use 'flex' for training")
            self.attn_op = flash_attn_func
""",
        path,
    )
    path.write_text(text, encoding="utf-8")


def _git(upstream: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(upstream), *args], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-dir", type=Path, required=True)
    args = parser.parse_args()
    upstream = args.upstream_dir.resolve()
    if not (upstream / ".git").is_dir():
        raise FileNotFoundError(f"Not a git checkout: {upstream}")
    commit = _git(upstream, "rev-parse", "HEAD")
    if commit != EXPECTED_COMMIT:
        raise RuntimeError(
            f"Expected upstream commit {EXPECTED_COMMIT}, found {commit}. "
            "Use bootstrap_upstream.sh so patch anchors and behavior are reproducible."
        )
    allowed_modified = {
        "wan_va/configs/__init__.py",
        "wan_va/dataset/__init__.py",
        "wan_va/modules/model.py",
        "wan_va/train.py",
    }
    modified = {
        line[2:].strip()
        for line in _git(upstream, "status", "--porcelain", "--untracked-files=no").splitlines()
        if line
    }
    unexpected = modified - allowed_modified
    if unexpected:
        raise RuntimeError(
            f"Refusing to patch a checkout with unrelated tracked changes: {sorted(unexpected)}"
        )

    bundle = Path(__file__).resolve().parent / "upstream"
    copies = {
        bundle / "segment_dataset.py": upstream / "wan_va/dataset/segment_dataset.py",
        bundle / "va_so101_reasoning_cfg.py": upstream / "wan_va/configs/va_so101_reasoning_cfg.py",
        bundle / "va_so101_reasoning_train_cfg.py": upstream
        / "wan_va/configs/va_so101_reasoning_train_cfg.py",
    }
    for source, destination in copies.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    _patch_dataset_init(upstream / "wan_va/dataset/__init__.py")
    _patch_configs_init(upstream / "wan_va/configs/__init__.py")
    _patch_train(upstream / "wan_va/train.py")
    _patch_optional_flash_attention(upstream / "wan_va/modules/model.py")
    print(f"Installed SO-101 segment adapter into {upstream} at {commit}.")


if __name__ == "__main__":
    main()
