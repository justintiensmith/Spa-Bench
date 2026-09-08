# Software and hardware environment

## Recorded environment

- LeRobot base: v0.6.0 (`30da8e687a6dfc617fcd94afc367ac7071c376ce`)
- Spa-Bench rollout fork revision:
  `88d519ec5872020cac210aa2d7c6b161cc3a0afe`
- Robot: SO-101 follower with six absolute joint-position channels
- Policy-facing cameras: fixed middle view and wrist-mounted view
- Training hardware recorded in current methods: four NVIDIA GH200 Grace Hopper
  Superchips, per-device batch size 24, global batch size 96

## Analysis dependencies

Python scripts collectively use NumPy, pandas, PyArrow, openpyxl, Pillow,
ReportLab, Hugging Face Hub, and LeRobot. Some historical JavaScript workbook
scripts use `@oai/artifact-tool`; replace or document that dependency before
claiming one-command public reproduction.

## Missing

- Exact Python and CUDA versions for each training run.
- Resolved package lock files or exported environments.
- Exact accelerator and cluster job metadata for each model.
- VLA-0 training/service environment revision.
- Portable dependency instructions for the JavaScript workbook tools.
- Safe-to-publish robot calibration and camera-device configuration.

