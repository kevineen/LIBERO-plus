# bank / 05 — hard（発展・任意）

解答の目安は gate [a05](../../answers/a05_parc_transfer.md) の T2 と同趣旨。

<!-- id: q05h-01  tags: [attention, failure, ood]  difficulty: hard  concept: 05 -->
**H1.** Language hard で SR=0。`*_attn.mp4` では指示対象付近が熱い。次に疑うべきことの優先順位として最も妥当なのはどれか。

- A. 注視が熱いのでモデルは正しい → 親 ckpt を差し替える
- B. 語彙 OOD・行動頭・chunk/open-loop など「見ていても死ぬ」系を疑い、薄い 0 だけで長い FT を決めない
- C. Evo-1 の FlashAttn を入れれば注視が消えて成功する
- D. `save_attention` を成功時のみに切り替えて再評価する
