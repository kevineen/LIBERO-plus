# q01 — VLA 経路と推論時契約

教材: [study/01_vla_pathways.md](../study/01_vla_pathways.md)  
解答: [answers/a01_vla_pathways.md](answers/a01_vla_pathways.md)（解いてから）

## 選択問題

**Q1.** TurboVLA が主張する経路に最も近いのはどれか。

- A. 視覚を必ず巨大 LLM のトークン空間に射影してから行動を出す（V→L→A）
- B. 視覚と言語を独立エンコードし、軽量相互作用のあと行動を出す（V+L→A）
- C. 言語だけから行動を出し、画像は使わない
- D. 強化学習のみで行動を学習し、模倣データは使わない

**Q2.** action chunk の説明として正しいものはどれか。

- A. 常に 1 ステップだけ出力する単位のこと
- B. 未来複数ステップ分のアクション列をまとめて出すこと
- C. データセットのエピソード ID のこと
- D. GPU のメモリチャンク割り当てのこと

**Q3.** TurboVLA の LIBERO 評価で推奨される関係はどれか。

- A. `chunk_size` は無視してよい
- B. `num_open_loop_steps` は常に 1 に固定
- C. `chunk_size == num_open_loop_steps` にする
- D. open-loop は学習時だけ使い評価では使わない

**Q4.** policy と sim を別プロセス（例: WebSocket）にする主な利点はどれか。

- A. 必ず成功率が 100% になる
- B. 依存スタックの衝突回避やホスト役割分担がしやすい
- C. データセットが自動で LeRobot 形式になる
- D. LIBERO-plus の摂動が不要になる

**Q5.** Evo-1 の典型的な評価構成に近いものはどれか。

- A. 単一プロセスで学習と MuJoCo を必ず同居させる
- B. `Evo1_server.py`（政策）と client（sim）を分ける
- C. ブラウザだけで政策を実行する
- D. テキストログだけで行動を決める（画像なし）

## 短答

**S1.** V→L→A が推論コストで不利になりやすい理由を 1–2 文で。

**S2.** `chunk_size=8` なのに `num_open_loop_steps=16` だと何がまずいか。

**S3.** PARC のホスト分割（例: thor で政策、別マシンで MuJoCo）と、Evo-1 の WS 分離の共通点を 1 文で。
