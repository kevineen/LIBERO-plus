# 05. PARC への落とし込み

調査正本: [parc/docs/00_research/turbovla_evo1.md](../parc/docs/00_research/turbovla_evo1.md)

対応クイズ: [quiz/q05_parc_transfer.md](../quiz/q05_parc_transfer.md)

## 目標

- **借りる優先度 P0 / P1 / P2** を自分の言葉で言える
- **借りないこと**と理由を言える
- 実装ジョブ（アダプタ・フル FT・thick eval）は学習完了後も **別承認**だと分かる

## 読むもの

| 優先 | リソース |
|------|----------|
| Must | [turbovla_evo1.md](../parc/docs/00_research/turbovla_evo1.md) 全文 |
| Must | [baselines/evo1/README.md](../parc/docs/baselines/evo1/README.md) |
| Should | [feature/vr-teleop/roadmap-data-quality.md](../parc/feature/vr-teleop/roadmap-data-quality.md) の M5（idle / stats_key） |
| Should | [catchup/05_adaptability.md](../parc/catchup/05_adaptability.md) |

## 要点 — 借りる

### P0（Evo-1）

1. **LIBERO-plus 評価ハーネス**（`libero-plus-eval/`・WS・7 カテゴリ）  
   → 外部天井・Camera/Robot 弱点の対照。記録は baselines 枠。親判定外。
2. **二段階 FT の仮説**（Stage1 expert → Stage2 フル）  
   → Language / semantic。YAML 草案あり、**実行は別承認**。cam FT 禁止維持。

### P1（TurboVLA / 両方）

1. **no-noop + mixed stats / versioned `stats_key`** → VR データ品質 M5
2. **policy ≠ sim プロセス分離** → thor / winpc / nuc の役割と整合
3. **評価プロトコル監査** → chunk=open-loop、action 次元 crop、gripper 二値化を parc-eval チェック項目に

### P2（将来）

- pad-to-24D + masks、TurboVLA 効率サイドカー全体、Jetson / evo1-lerobot

## 要点 — 借りない

| やらない | 理由 |
|----------|------|
| TurboVLA を親にする | LeRobot 非対応・plus なし・スタック別 |
| Evo-1 を即親にする | サイドカー契約・Camera deep 等ゲート未クリア |
| RoboTwin 即追従 | 本戦場外 |
| RLDS 全置換 | VR→LeRobot v3 と逆方向 |

## 手を動かすメモ

次の対応表を notebook かメモに埋める（コピペ可・自分の一文で）。

| 上流の技法 | PARC での置き場所 | 今すぐやる？ |
|------------|-------------------|--------------|
| libero-plus-eval WS | baselines / 将来の対照 eval | 承認後 |
| 二段階 FT | sidecar YAML → 実行は承認後 | 草案のみ可 |
| no-noop / stats_key | VR roadmap M5 | M0 E2E 後 |
| プロセス分離 | Fleet・ホスト役割 | 運用で既に近い |
| TurboVLA 全体を親 | — | **しない** |

## 完了条件

- [ ] P0/P1 と「借りない」を turbovla_evo1.md と対応付けて説明できる
- [ ] [q05](../quiz/q05_parc_transfer.md) を解いた
- [ ] [study/README.md](README.md) の完了チェックリストを更新した
- [ ] 点数を [rubric](../quiz/rubric.md) で判定し、必要なら下記へ

## つまずいたら

- 易しい補足: [remediation/05/](remediation/05/)
- 復習クイズ: [quiz/bank/05/easy.md](../quiz/bank/05/easy.md)
- 判定: [quiz/rubric.md](../quiz/rubric.md)

## このトラックの終わり

実装に進むときは:

1. strategy / playbook で承認を取る
2. 重い GPU は thor 既定（`parc/strategy/04_machine_roles.md`）
3. 親 ckpt の差し替えは薄い eval だけでは決めない（decision rules）

お疲れさまです。
