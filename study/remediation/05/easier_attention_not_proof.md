<!-- tags: [attention, failure, saliency] -->
# もっと易しく: 注視マップ ≠ 本当の「注意の重み」

## 比喩

試合映像に「選手がどこを見ていたか」のヒートマップを重ねる。  
それは審判の最終判定（親 ckpt 差し替え）ではなく、**敗因の仮説メモ**。

## 要点

1. `save_attention` は SmolVLA の **vision 活性化 / Grad-CAM** オーバーレイ（失敗時のみが既定）
2. 真の cross-attention や「因果証明」ではない。見ていても行動が死ぬこともある
3. 既存の失敗動画レビュー（`save_video`）の隣に置く。薄い SR=0 だけで親を決めない

## 反例

注視が物体上にある → モデルは正しい、は飛躍。語彙 OOD でも起きうる。

戻る: [05_parc_transfer.md](../../05_parc_transfer.md) · 手順: [docs/04_eval.md](../../../parc/docs/04_eval.md)
