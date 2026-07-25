# Experiment claims（任意）

複数 PC で同じ sweep を同時に回さないための軽い宣言ボードです。

1. `example.claim.yaml` をコピーして `<sweep>__<machine>.claim.yaml` を作る
2. `owner` / `machine` / `sweep` / `status` を埋める
3. 実行前に他メンバーの claim を確認する

自動化チェックは後続。衝突防止の本丸は **PC ごとの `experiments_dir`** と **`PARC_MACHINE_ID` 付き run_id** です。
