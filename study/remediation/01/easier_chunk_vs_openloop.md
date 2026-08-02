<!-- tags: [chunk, open-loop] -->
# もっと易しく: action chunk と open-loop

## 比喩

レストランで **コース料理を一度に注文する**のが chunk。  
厨房に何度も聞きに行かず、出てきた皿を順番に出すのが open-loop 実行。

- chunk =「何品まとめて計画したか」
- open-loop steps =「計画を聞き直さずに何品出すか」

評価では **注文数と提供数を同じ**にする（例: 両方 12）。

## 要点

1. 政策はしばしば未来 H ステップ分を一度に出す
2. `chunk_size != num_open_loop_steps` だと、論文・学習時と別ゲームになる
3. open-loop が chunk より長いと、計画していない区間まで見切り発車になる

## 反例

「open-loop = 学習しない」ではない。評価時の **実行の仕方**の話。

戻る: [01_vla_pathways.md](../../01_vla_pathways.md)
