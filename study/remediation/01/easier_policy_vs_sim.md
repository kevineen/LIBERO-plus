<!-- tags: [ws, process-split] -->
# もっと易しく: policy と sim を分ける

## 比喩

ゲーム本体（sim / ロボット）と、頭脳（policy）を **別アプリ**にする。  
電話（WebSocket）で「今の画面」を送り、「次の操作」をもらう。

## 要点

1. GPU 付き頭脳と、物理シミュを別プロセス／別マシンに置ける
2. Python 依存が衝突しにくい（Evo-1 公式も server ↔ client）
3. PARC の thor（政策）と winpc/nuc（MuJoCo）分割と同じ発想

## 反例

分けただけで成功率は上がらない。分け方は **運用・再現性**の話。

戻る: [01_vla_pathways.md](../../01_vla_pathways.md)
