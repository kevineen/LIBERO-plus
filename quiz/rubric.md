# 採点ルーブリック（理解度 → 次アクション）

gate クイズ（`q01`〜`q05`）の自己採点結果から、次に何をするかを決める正本です。

## 選択問題の正答率

短答は「要点が書けていれば OK / 用語取り違えは NG」でざっくり判定する。

| 選択正答率 | 短答 | 判定 | 次にやること |
|-----------|------|------|----------------|
| ≥ 85% | OK | **定着** | 次 Phase。余力があれば `bank/XX` に hard を足して挑戦 |
| 70–84% | OK 寄り | **合格・弱点あり** | 誤答タグだけ [`study/remediation/`](../study/remediation/) → [`bank/XX/easy`](bank/) を解く |
| 40–69% | あやしい | **要復習** | 本線の再読より先に remediation の易しい補足 → easy → gate 再挑戦 |
| &lt; 40% | NG | **前提不足** | [00_prerequisites](../study/00_prerequisites.md) / [catchup](../parc/catchup/) / 用語へ戻る |

q04 / q05 のトラブルシュート記述が妥当なら、境界（例: 68%→合格寄り）で加点してよい。

## 新しい教材・クイズを足す手順

誤答ログ（[`progress/`](progress/)）を見て:

1. **タグを1つ**決める（例: `chunk`, `stats_key`, `stage1`）
2. `study/remediation/0X/` に「比喩 + 要点≤3 + 反例1」の短文を追加（無ければ）
3. `quiz/bank/0X/easy.md` に **選択2 + 短答1** を追加（メタコメント付き）
4. `bank/0X/answers.md` を更新
5. 再テストは追加分のみ。gate を書き直さない

エージェントに頼むときのプロンプト例:

```text
quiz/progress の最新ログを見て、wrong_tags 向けに
remediation 短文と bank easy 3問を追加して。
gate 本体は変更しないで。
```

## 完了との関係

- Phase 完了の最低ライン: ルーブリックで **合格（≥70%）** かつ短答 OK、または remediation+easy 後に再測して合格
- 満点は不要

関連: [quiz/README.md](README.md) · [study/README.md](../study/README.md)
