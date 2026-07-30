# 06. PARC2026 準備チェックリスト

公式: https://weblab.t.u-tokyo.ac.jp/physical-ai-competition/  
説明会資料: https://drive.google.com/drive/folders/1-gTOKG5uEXjkmphKJSCo9mCmSCEGbOtI

新規メンバー向けの概念・学習 URL・初回実行は [catchup/](../catchup/) を参照。

## 公開情報（2026-06 説明会）

- 評価環境: **LIBERO / LIBERO-Plus（7 摂動）**
- 指標: Success / 滑らかさ(Jerk 等) / 実行効率 / 安全性（重み非公開）
- 予選: I/O 合わせ低性能モデル + 評価環境 + **提出用ファイル**
- 本選: RTX PRO 6000 + Pi0/Gr00t 学習コード + 提出用ファイル（形式は予選と同様）

## ルール前に完了しておくこと

- [ ] `scripts/setup_env.sh` で assets / `~/.libero` が plus を向く
- [ ] `parc-eval` でスモーク成功率（ランダムでほぼ 0 でよい）が保存される
- [ ] `subset_eval` でカテゴリ別メトリクスが読める
- [ ] `parc-train` dry-run で学習コマンドが生成される
- [ ] データ置き場・実験置き場のディスク計画（`paths.yaml`）

## 配布物が来たらやること

1. 提出テンプレのディレクトリ構造を `docs/submission_spec.md` にメモ  
2. `parc.policies.build_policy` に公式 I/O アダプタを実装  
3. `train.backend` に Pi0 / Gr00t を接続  
4. 予選 Track の task リストを `configs/experiments/parc_prelim.yaml` に固定  
5. ローカル subset → 配布評価環境の順で差分を確認  

## 提出（予定）

```text
（配布テンプレ）
  ├── policy / checkpoint
  ├── infer entrypoint
  └── config
→ 運営指定のアップロード
```

詳細は未発表のため、**このリポジトリでは提出 zip を捏造しません**。  
テンプレが届いたら `scripts/pack_submission.sh` を追加する想定です。
