# q02 — TurboVLA

教材: [study/02_turbovla.md](../study/02_turbovla.md)  
解答: [answers/a02_turbovla.md](answers/a02_turbovla.md)

## 選択問題

**Q1.** TurboVLA の視覚エンコーダとして README で主に言及されるのはどれか。

- A. InternVL3-1B のみ
- B. DINOv3
- C. CLIP だけを必須とする公式唯一経路
- D. 画像エンコーダを使わない

**Q2.** `*_no_noops` データが狙うことはどれか。

- A. 言語指示をすべて削除する
- B. ほぼ静止などの no-op ステップを減らしたデモにする
- C. カメラ台数を必ず 1 に固定する
- D. LIBERO-plus の 7 摂動をすべて合成する

**Q3.** `stats_key` の役割に最も近いのはどれか。

- A. Git のコミットハッシュの別名
- B. どの正規化統計で normalize / denormalize するかを明示するキー
- C. WebSocket のポート番号
- D. MuJoCo のタイムステップ dt

**Q4.** TurboVLA 論文・README の LIBERO 主戦場はどれか。

- A. LIBERO classic 4-suite
- B. LIBERO-plus のみ
- C. Meta-World のみ
- D. 実機 SO100 のみ

**Q5.** PARC が TurboVLA「全体を親にする」のを避ける理由として適切なものはどれか。

- A. 成功率が公式に 0% だから
- B. LeRobot 非対応・plus なし・スタックが別だから
- C. Python が使えないから
- D. action chunk が存在しないから

**Q6.** 言語エンコーダについて README が述べていることに近いのはどれか。

- A. BERT はオンラインで動き、テキスト特徴キャッシュは不要
- B. 言語は一切使わない
- C. 必ずオフラインで全文を事前埋め込みキャッシュ必須
- D. 言語は GPT-4 API のみ

## 短答

**S1.** mixed-suite stats を取る理由を 1–2 文で。

**S2.** PARC の VR データ品質（M5）に翻訳すると、TurboVLA のどの技法に対応するか。

**S3.** 推論 VRAM &lt;1GB を狙う設計上の要点を 1 文で。
