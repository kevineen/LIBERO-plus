# Playbook: ジョブ完了後（Discord DONE / ユーザー報告）

## 1. マシンと job を特定

通知例:

```text
[PARC] DONE · q_...
machine=winpc  kind=eval  phase=done ...
```

- 表示名 `PARC · <machine>` と `machine=` を正とする
- Hub UI が thor でも、実行は winpc のことがある

## 2. 結果を読む

```bash
cd /home/kevin/Matsuo/robot/LIBERO-plus/parc
set -a && source .env.local && set +a
uv run parc-queue status --limit 8

# run_id は queue JSON / registry / experiments 直下
python3 <<'PY'
import json, pathlib
rid = "REPLACE_RUN_ID"
m = json.load(open(f"experiments/{rid}/metrics.json"))
print("SR", m.get("success_rate"), "n", m.get("n_episodes"))
for k,v in sorted((m.get("by_category") or {}).items()):
    print(f"  {k}: {v.get('success_rate'):.3f} (n={v.get('n')})")
PY
```

thor なら SSH 先の `/mnt/sda/parc_libero_plus/experiments/<run_id>/metrics.json`。

train 完了なら checkpoints の有無も確認:

```bash
ls experiments/<run_id>/train_output/checkpoints/
```

## 3. 判断（05 に従う）

| 完了したもの | 次 |
|--------------|-----|
| 薄い eval のみ | 親決め・長い FT に進まない。厚い eval を積むか提案 |
| 厚い eval | `02` の表を更新。親 ckpt を `05` の条件で再評価 |
| Camera 深掘り | task 別 SR と動画パスを `02` に追記 |
| FT + 薄い eval | 厚い eval を追加投入（承認後） |
| failed | ログを見て再キュー or 修正。安易な同設定リトライはしない |

## 4. strategy 更新

→ [update_strategy_docs.md](update_strategy_docs.md)

最低限:

- `01` の running/queued
- `02` に SR・カテゴリ・run_id
- `03` のチェックボックス

## 5. ユーザーへの返答テンプレ

```text
完了: <host> / <job or run> / SR=<...>（厚い|薄い|深掘り）
要点: <1行>
strategy: 01/02/03 を更新
次: <提案 1 つだけ> — 投入してよければ言ってください
```

次ジョブを **勝手に enqueue しない**（ユーザーが「続けて」「投げて」と言った場合のみ）。
