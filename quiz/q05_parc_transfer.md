# q05 — PARC 落とし込み

教材: [study/05_parc_transfer.md](../study/05_parc_transfer.md)  
解答: [answers/a05_parc_transfer.md](answers/a05_parc_transfer.md)

## 選択問題

**Q1.** P0 として優先される Evo-1 由来の借り物に含まれるのはどれか。

- A. RoboTwin 即追従を親ラインにする
- B. LIBERO-plus 評価ハーネスと二段階 FT 仮説
- C. RLDS への全データ置換
- D. TurboVLA を即親 ckpt にする

**Q2.** P1 のデータ衛生として適切なものはどれか。

- A. no-noop / idle trim と versioned `stats_key`
- B. すべてのデモを手作業で削除する
- C. 正規化統計を毎回ランダムに作り直してキーを付けない
- D. 言語指示を空文字に統一する

**Q3.** 「Evo-1 を即親にしない」理由に近いのはどれか。

- A. 論文が存在しないから
- B. サイドカー契約・Camera deep 等のゲート未クリア
- C. WebSocket が発明されていないから
- D. LeRobot という語が禁止されているから

**Q4.** TurboVLA を親にしない理由として教材が挙げるものに含まれるのはどれか。

- A. LeRobot 非対応・plus なし・スタック別
- B. パラメータが多すぎて 100B 超だから
- C. 画像を一切使わないから
- D. オープンソースでないから（実際は公開実装あり）

**Q5.** 二段階 FT の実走について正しい運用はどれか。

- A. 学習トラック完了と同時に、承認なしで本番親を差し替えてよい
- B. YAML 草案はあっても実行は別承認、薄い eval だけで親を決めない
- C. cam FT を必ず同時に必須化する
- D. strategy を読まずに thor 全 GPU を占有してよい

**Q6.** SmolVLA の失敗エピソードで `eval.save_attention: true` が出すものとして正しいのはどれか。

- A. 真の cross-attention 重みそのもの（FlashAttn 必須）
- B. vision 活性化（または Grad-CAM）のオーバーレイ動画。既定は失敗時のみ · 仮説生成用
- C. 親 ckpt を自動で差し替えるゲート信号
- D. Evo-1 WS サーバの attn ログを thin client 経由で取得したもの

## 短答

**S1.** P0 を 2 項目、キーワードだけで列挙せよ。

**S2.** P1 の「プロセス分離」が PARC のどの運用と整合するか、1 文で。

**S3.** 「借りない」表から 1 つ選び、理由を自分の言葉で。

**S4.** 注視マップ動画の向きについて、env RGB と方策入力（flip）の関係を 1 文で。

## トラブルシュート / 対応付け

**T1.** チームが「TurboVLA の 97.7% が出たから親を差し替えたい」と言った。あなたはどう答えるか（2–4 文）。観点: ベンチ差・データ形式・ゲート・サイドカー。

**T2.** Language hard で SR=0。注視オーバーレイは対象物体付近が熱い。次に何を疑うか（2–3 文）。
