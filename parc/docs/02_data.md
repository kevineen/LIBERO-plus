# 02. 学習データ

## 公式に近いデータセット

| 形式 | Hugging Face | 用途 |
|------|----------------|------|
| LeRobot | [`lerobot/libero_plus`](https://huggingface.co/datasets/lerobot/libero_plus) | `lerobot-train` |
| LeRobot | [`Sylvest/libero_plus_lerobot`](https://huggingface.co/datasets/Sylvest/libero_plus_lerobot) | 同上（著者版） |
| RLDS | [`Sylvest/libero_plus_rlds`](https://huggingface.co/datasets/Sylvest/libero_plus_rlds) | OpenVLA-OFT 系 |
| 4suite 分割 | [`Sylvest/libero_plus_data_4suite`](https://huggingface.co/datasets/Sylvest/libero_plus_data_4suite) | suite 別実験 |

参考重み（mix-SFT）:  
[`Sylvest/openvla-7b-oft-finetuned-libero-plus-mixdata`](https://huggingface.co/Sylvest/openvla-7b-oft-finetuned-libero-plus-mixdata)

## 置き場所

デフォルトは `parc/data/datasets/`。  
ディスク逼迫時は `configs/paths.yaml` の `data_dir` を `/mnt/sda/...` などに変更。

```bash
export HF_HOME=/mnt/sda/huggingface   # 既に使っているならそのまま
```

## 取得例

```bash
# メタだけ確認
huggingface-cli download lerobot/libero_plus --repo-type dataset --include README.md --local-dir data/datasets/libero_plus_meta

# 実学習時は LeRobot が自動キャッシュすることが多い
# 事前に全部落とす場合は容量に注意（数十 GB 級になり得る）
```

## PARC 本選データ

説明会では **Franka Panda 学習データ** と **Pi0 / Gr00t ベースライン** が配られるとあります。  
配布後は:

1. `data/datasets/parc_official/` に置く  
2. `configs/experiments/*.yaml` の `dataset_repo_id` / パスを差し替え  
3. `train.backend` を `openpi` / `gr00t` 等にして `parc.train` を拡張  

今は公開 LIBERO-plus データで **パイプライン動作確認** をする段階です。

## オリジナルデータの追加

自前デモの LeRobot 変換、ローカル `dataset_root`、混合学習、評価スキーマ互換の手順は次を参照:

→ **[07_custom_data_and_algos.md](07_custom_data_and_algos.md)**
