# LeRobot rollout and VLA-0 integration

The integration is maintained separately from this thesis-artifact repository:

- Fork: https://github.com/justintiensmith/lerobot_rollout_vla0
- Integration revision: `88d519ec5872020cac210aa2d7c6b161cc3a0afe`
- Upstream base: LeRobot v0.6.0,
  `30da8e687a6dfc617fcd94afc367ac7071c376ce`

The two commits above the base add:

- an inference-only LeRobot adapter for a VLA-0 HTTP service;
- synchronous and queued asynchronous inference support;
- CSV-backed per-episode prompt schedules for episodic rollout;
- documentation and tests.

`patches/` contains Git-generated patch exports for those committed changes.

## GR00T action filtering

`groot_ema_runtime_working.patch` records the currently uncommitted
deployment-time EMA action filter. It should not be described as part of the
published fork until it is reviewed, tested, committed, and linked by immutable
revision. The final record must also include the coefficient used in the
reported rollouts.

