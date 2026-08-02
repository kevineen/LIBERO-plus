<!-- tags: [server-first, ports] -->
# もっと易しく: server を先に起動する

## 比喩

電話の受付（policy server）を開けてから、客（sim client）がかける。  
受付が閉まっていると「接続できない」。

## 要点

1. Evo-1 はだいたい `Evo1_server.py` が先
2. ポート番号が server / client で一致しているか見る
3. Phase 4 はフル学習ではなく smoke（起動確認や少数 trial）でよい

## 反例

client だけ先に連打しても、server が無ければ学習にはならない。

戻る: [04_upstream_smoke.md](../../04_upstream_smoke.md)
