# TurboVLA / Evo-1 — PARC 向け参照メモ

時点: **2026-08-03**  
出典: [TurboVLA](https://github.com/H-EmbodVis/TurboVLA) · [Evo-1](https://github.com/MINT-SJTU/Evo-1)  
位置づけ: **調査メモ（非オペ正本）**。親 = SmolVLA continue10k の差し替え候補ではない。

関連成果物:

| 成果物 | パス |
|--------|------|
| Evo-1 plus ベースライン枠 | [docs/baselines/evo1/](../baselines/evo1/) |
| 二段階 FT YAML 草案 | `configs/experiments/sidecar_smolvla_ft_twostage_stage{1,2}_*.yaml` |
| VR idle/noop · stats_key | [feature/vr-teleop/roadmap-data-quality.md](../../feature/vr-teleop/roadmap-data-quality.md)（M5） |

---

## 結論

両方とも参考価値あり。主線は触らない。

- **Evo-1** → 運用・評価・言語軸（LIBERO-plus 公式 eval、WS 分離、二段階 FT、LeRobot I/O）
- **TurboVLA** → データ衛生・超軽量推論（no-noop、mixed stats、open-loop=chunk、V+L→A）

PARC 接点: Phase D（Language / Sensor / VR）、サイドカー先例（MolmoAct2 · QuantVLA · CLAIR）。

---

## 比較（短表）

| 観点 | TurboVLA | Evo-1 | PARC 主線 |
|------|----------|-------|-----------|
| 経路 | **V+L→A**（LLM 非中心） | InternVL3-1B + action expert | SmolVLM + flow-matching |
| 規模 | 0.2B / ~31ms / ~0.9GB / ~32Hz（4090） | ~0.77B · LeRobot 統合 | 中間・FT 済み |
| データ | TFDS/RLDS `*_no_noops` | LeRobot v2.1 | LeRobot（VR は v3） |
| LIBERO | classic 4-suite（論文 97.7%） | classic + **LIBERO-plus 公式** | plus が本戦場 |
| デプロイ | 同期チャンク · RoboTwin 別 Python | **WS server↔client** · Jetson · SO100 | Fleet + Quest |

---

## 借りる優先度

### P0 — Evo-1

1. **LIBERO-plus 評価ハーネス**（`libero-plus-eval/` · 7 カテゴリ · WS）  
   公開平均 ~65.7%、Camera ~45% / Robot ~49% → PARC の Camera/Sensor 弱点と重なる外部天井。  
   記録枠: [baselines/evo1](../baselines/evo1/README.md)（親判定外）。
2. **二段階 FT**（Stage1: VLM 凍結 · Stage2: フル）  
   Phase D1 Language OOD / semantic 保持の仮説。YAML 草案あり · **実行は別承認**。

### P1 — TurboVLA / 両方

1. **no-noop 除去 + mixed-suite stats**（`regenerate_libero_no_noops.py` · `compute_mixed_stats.py` · `libero_all4_stats.json`）  
   VR デモ idle trim + versioned `stats_key` として M5 に接続（classic RLDS 全置換はしない）。
2. **policy ≠ sim プロセス分離**（WS / 別 Python）— thor policy / winpc·nuc MuJoCo と整合。
3. **評価プロトコル細部** — `chunk_size == num_open_loop_steps`、action 次元 crop · gripper 二値化を `parc-eval` 監査項目に。

### P2 — 将来

- Evo-1 pad-to-24D + image/action mask（多エンボディメント）
- TurboVLA 全体を効率サイドカー（&lt;1GB が必要になったときだけ）
- Jetson / `evo1-lerobot`

---

## 借りない

| やらないこと | 理由 |
|--------------|------|
| TurboVLA を親にする | LeRobot 非対応 · plus なし · スタック別 |
| Evo-1 を即親にする | サイドカー契約（Camera deep 等のゲート未クリア） |
| RoboTwin 即追従 | 本戦場外 |
| RLDS 全置換 | VR→LeRobot v3 と逆方向 |

---

## 落とし込みチェック

- [x] 本メモ（`00_research/`）
- [x] Evo-1 baselines 枠 + 公開数字 · 再現手順
- [x] SmolVLA 二段階 FT YAML 草案（dry_run / 承認待ち）
- [x] VR roadmap M5 に idle/noop + `stats_key` を追記
- [ ] Evo-1 実測 thin/hard（GPU · **別承認**）
- [ ] 二段階 FT 実走（**別承認** · cam FT 禁止維持）
- [ ] M0 Quest E2E 後に noop trim 実装

---

## 学習トラック

概念 → 上流 smoke → PARC 落とし込みの教材・クイズ:

- 入口: [`study/README.md`](../../../study/README.md)
- クイズ: [`quiz/README.md`](../../../quiz/README.md)
