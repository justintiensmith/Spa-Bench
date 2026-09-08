#!/usr/bin/env python
"""Create a lightweight local LingBot-VA model view with attn_mode=flex."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _relative_symlink(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if not destination.is_symlink() or destination.resolve() != source.resolve():
            raise RuntimeError(f"Refusing to replace an unrelated training-view path: {destination}")
        return
    target = os.path.relpath(source.resolve(), destination.parent.resolve())
    destination.symlink_to(target, target_is_directory=source.is_dir())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    config_source = source / "transformer/config.json"
    config_output = output / "transformer/config.json"
    if not config_source.is_file():
        raise FileNotFoundError(config_source)
    if output == source:
        raise ValueError("--output must differ from --source; the downloaded base model is kept unchanged.")
    output.mkdir(parents=True, exist_ok=True)

    for child in source.iterdir():
        destination = output / child.name
        if child.name == "transformer":
            destination.mkdir(parents=True, exist_ok=True)
            for transformer_child in child.iterdir():
                if transformer_child.name == "config.json":
                    continue
                target = destination / transformer_child.name
                _relative_symlink(transformer_child, target)
        else:
            _relative_symlink(child, destination)

    config = json.loads(config_source.read_text(encoding="utf-8"))
    config["attn_mode"] = "flex"
    config_output.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "TRAINING_VIEW.json").write_text(
        json.dumps(
            {"source": str(source), "attn_mode": "flex", "weights_are_symlinked": True},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Created flex-attention training view at {output}")


if __name__ == "__main__":
    main()
