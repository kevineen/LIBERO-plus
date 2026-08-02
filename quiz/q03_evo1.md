# q03 — Evo-1

教材: [study/03_evo1.md](../study/03_evo1.md)  
解答: [answers/a03_evo1.md](answers/a03_evo1.md)

## 選択問題

**Q1.** Evo-1 の Stage1 で主に学習するものに近いのはどれか。

- A. シミュレータの物理エンジンパラメータのみ
- B. integration / action expert 側（VLM は凍結寄り）
- C. 必ず VLM のみをフル学習し expert は触らない
- D. データセットの zip 圧縮率

**Q2.** Stage2 の特徴として正しいものはどれか。

- A. 学習を一切行わない評価専用ステージ
- B. VLM も含めたフル寄りの finetune
- C. no-noop データの生成スクリプトのこと
- D. Quest 3 のファームウェア更新

**Q3.** `action_mask` / `image_mask` の目的に近いのはどれか。

- A. 損失計算や有効入力を、パディング次元・無効カメラから守る
- B. PNG のアルファチャンネルを保存する
- C. SSH 鍵のパスフレーズを隠す
- D. LIBERO のスイート名を暗号化する

**Q4.** 著者公表の LIBERO-plus 平均成功率のオーダーとして教材が示すのはどれか。

- A. 約 10%
- B. 約 66%
- C. 約 99%
- D. 約 0%

**Q5.** Camera 摂動の公表数字の読み方として適切なものはどれか。

- A. Camera は常に 95% 超で弱点ではない
- B. Camera / Robot が相対的に弱く、PARC の弱点と重なりうる
- C. Camera は評価対象外
- D. Camera は言語指示の別名である

**Q6.** 公式の自前データ学習形式として README が示すのはどれか。

- A. 独自バイナリのみ
- B. LeRobot v2.1
- C. 音声 WAV のみ
- D. Excel CSV のみ

## 短答

**S1.** 二段階 FT が「意味整合の維持」に効く、とされる直感を 1–2 文で。

**S2.** PARC に `policy.type=evo1` が未実装のとき、評価はどう進めるか。

**S3.** pad-to-24D が便利な状況を 1 つ挙げる。
