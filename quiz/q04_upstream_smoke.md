# q04 — Upstream smoke

教材: [study/04_upstream_smoke.md](../study/04_upstream_smoke.md)  
解答: [answers/a04_upstream_smoke.md](answers/a04_upstream_smoke.md)

## 選択問題

**Q1.** 本トラック Phase 4 の必須完了条件に含まれるのはどれか。

- A. TurboVLA 80k step のフル学習完了のみ
- B. smoke（server 起動や少数 trial eval）または GPU 無しウォークスルー記録
- C. RoboTwin 50 タスク全制覇のみ
- D. PARC 親 ckpt の差し替え完了のみ

**Q2.** Evo-1 評価で先に起動すべきなのはどれか。

- A. 必ず client だけ
- B. policy server（例: `Evo1_server.py`）
- C. `git push --force`
- D. Quest のファクトリーリセット

**Q3.** TurboVLA `evaluate.py` で学習時と揃えるべきものの組はどれか。

- A. `stats_path` / `stats_key` と chunk / open-loop
- B. ランダムなポート番号だけ
- C. Wi-Fi SSID だけ
- D. ディスプレイ解像度だけ

**Q4.** thor 上の Evo-1 weights の想定パスに近いのはどれか（教材・baselines）。

- A. `/mnt/sda/parc_libero_plus/checkpoints/Evo1_LIBERO`
- B. `C:\Windows\System32`
- C. `/tmp` のみ（恒久保存先として推奨）
- D. Hugging Face にだけ存在しローカル禁止

**Q5.** flash-attn インストールを飛ばすと README が警告しうることはどれか。

- A. 画面の色が変わるだけ
- B. 成功率低下や動作不安定のリスク
- C. 必ずディスクが暗号化される
- D. MuJoCo のライセンスが無効になる

## 短答

**S1.** GPU が無くても Phase 4 を完了とみなすために notebook へ書くべき内容を 2 つ挙げる。

**S2.** Evo-1 client が「接続できない」とき、最初に確認する項目を 2 つ。

## トラブルシュート

**T1.** TurboVLA 評価で `chunk_size=12`、`num_open_loop_steps=4` のままだった。何を直し、なぜか。
