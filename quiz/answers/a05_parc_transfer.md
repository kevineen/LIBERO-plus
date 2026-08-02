# a05 — 解答（PARC 落とし込み）

## 選択

| 問 | 正答 | 解説 |
|----|------|------|
| Q1 | **B** | plus harness + 二段階 FT 仮説が P0 |
| Q2 | **A** | no-noop/idle + versioned stats_key |
| Q3 | **B** | サイドカー契約・ゲート未クリア |
| Q4 | **A** | LeRobot/plus/スタックの不一致 |
| Q5 | **B** | 実行は別承認、薄い eval で親を決めない |

## 短答（模範）

**S1.** LIBERO-plus 評価ハーネス、二段階 FT 仮説。

**S2.** thor で政策・別ホストで MuJoCo / Fleet など、プロセスとマシン役割を分ける運用と整合する。

**S3.** 例: RLDS 全置換はしない — VR が LeRobot v3 方向だから逆流になる。

## トラブルシュート / 対応付け

**T1.（模範）** 97.7% は LIBERO **classic** 上の著者設定であり、PARC 本戦場の **LIBERO-plus** や自前データ契約とは別。TurboVLA は LeRobot 非対応でスタックも違う。親差し替えはサイドカー契約外で、Camera deep 等のゲートと parc-eval 同尺の証拠が先。まずは plus 対照やデータ衛生（noop/stats）として借りる。
