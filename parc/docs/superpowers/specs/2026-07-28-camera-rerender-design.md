# Camera viewpoint re-render → LeRobot（MVP）

日付: 2026-07-28

## Goal

Camera Viewpoints hard OOD（horizon/vertical 大）で SR=0 の壁を、sim state 再レンダで作った視点摂動デモで破る。

## Approach

1. 元 LIBERO spatial hdf5 の `states` + `actions` を読む
2. `OffScreenRenderEnv` に `_view_{h}_{v}_{scale}_{rot}_{vert}_initstate_0` 付き BDDL パスを渡し、`regenerate_obs_from_state` で agentview だけ摂動
3. 180° flip して LeRobot v3（front/wrist/state8/action7/task）に書く
4. +15k ckpt を親に短 FT（cam mix or cam-only）

## Train-safe view grid（eval 漏洩回避）

Eval exact: `11_15_100_0_0`, `13_15_100_0_0`, `14_15_100_0_0` は使わない。

Default grid:

- horizon ∈ {5, 8, 10, 12}
- vertical ∈ {5, 10, 15}
- scale=100, endpoint=(0,0)

## Success metric

Camera deep 610–612 で SR>0、厚い全体 SR を大きく落とさない。

## Scripts

- `parc/scripts/rerender_camera_demos.py` — LIBERO-plus `.venv` で staging（npz）
- `parc/scripts/staging_to_lerobot.py` — robot/parc `uv` で LeRobot 化
- FT YAML: `configs/experiments/smolvla_ft_camera_rerender_from15k_winpc.yaml`
