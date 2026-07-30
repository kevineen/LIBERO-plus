# 02. 勉強すべき URL

優先度順です。**Must を先に**、時間があれば Should / Optional へ。  
リンク切れに気づいたら PR / チャットで共有してください。

## Must（まずこれ）

| リソース | URL | 読み方のヒント |
|----------|-----|----------------|
| PARC 公式サイト | https://weblab.t.u-tokyo.ac.jp/physical-ai-competition/ | スケジュール・概要。ルール更新の一次情報 |
| PARC 説明会資料（Drive） | https://drive.google.com/drive/folders/1-gTOKG5uEXjkmphKJSCo9mCmSCEGbOtI | 評価指標の説明。`docs/06_competition.md` と併読 |
| LIBERO-plus 論文 | https://arxiv.org/pdf/2510.13626 | abstract・図・7 摂動・主要結果表 |
| LIBERO-plus サイト | https://sylvestf.github.io/LIBERO-plus | ベンチのビジュアル理解 |
| LIBERO（元ベンチ）リポジトリ | https://github.com/Lifelong-Robot-Learning/LIBERO | suite・タスクの前提知識 |
| Hugging Face LeRobot ドキュメント | https://huggingface.co/docs/lerobot | データ形式・学習の共通基盤 |
| SmolVLA（LeRobot） | https://huggingface.co/docs/lerobot/en/smolvla | いま parc が使う軽量 VLA |

## Should（線を通したあと・並行学習）

| リソース | URL | 用途 |
|----------|-----|------|
| LIBERO-plus GitHub | https://github.com/sylvestf/LIBERO-plus | インストール・評価の upstream |
| LIBERO-plus assets（HF Dataset） | https://huggingface.co/datasets/Sylvest/LIBERO-plus | `assets.zip` など |
| `lerobot/libero_plus`（学習データ） | https://huggingface.co/datasets/lerobot/libero_plus | FT 用（十数 GB 級） |
| Sylvest LeRobot 版データ | https://huggingface.co/datasets/Sylvest/libero_plus_lerobot | 著者配布の別経路 |
| Sylvest RLDS データ | https://huggingface.co/datasets/Sylvest/libero_plus_rlds | OpenVLA 系学習向け |
| OpenVLA-OFT+ 重み（参考） | https://huggingface.co/Sylvest/openvla-7b-oft-finetuned-libero-plus-mixdata | 論文リーダーボード上位の例 |
| OpenVLA | https://github.com/openvla/openvla | VLA の古典的実装 |
| OpenVLA-OFT | https://github.com/moojink/openvla-oft | OFT 系（plus 論文で頻出） |
| SmolVLA ベース重み | https://huggingface.co/lerobot/smolvla_base | FT の初期重み |
| SmolVLA 論文 | https://arxiv.org/abs/2506.01844 | 軽量 VLA の設計意図 |
| LeRobot GitHub | https://github.com/huggingface/lerobot | ソース・Issue |

## Optional（本選・深掘り）

| リソース | URL | 用途 |
|----------|-----|------|
| π₀ / openpi | https://github.com/Physical-Intelligence/openpi | 本選で想定される系統の理解 |
| MuJoCo | https://mujoco.org/ | シミュレータ背景（LIBERO が利用） |
| robosuite | https://robosuite.ai/ | LIBERO 周辺のマニピ環境 |
| Behavior Cloning 入門（Stanford CS231n 等の IL 章でも可） | 各自の講義資料 | 模倣学習の基礎 |
| 強化学習の超入門（任意） | 例: Spinning Up https://spinningup.openai.com/ | 後の GRPO/GSPO を読むとき |

## このリポジトリ内で読む順番

1. [catchup/01_concepts.md](01_concepts.md)（用語）
2. [docs/00_overview.md](../docs/00_overview.md)
3. [docs/06_competition.md](../docs/06_competition.md)
4. [docs/01_setup.md](../docs/01_setup.md) → [03_first_run.md](03_first_run.md) と並行
5. 余裕があれば [strategy/README.md](../strategy/README.md)（チームの現状判断）

## 学習の目安（初心者）

```text
Day 1: Must の公式・サイト・SmolVLA docs（斜め読み）+ concepts
Day 2: first_run（setup〜ランダム評価）
Day 3: SmolVLA smoke FT + ckpt eval + parc-list
以降: 論文を精読 / docs/07 以降 / strategy
```

次: [03_first_run.md](03_first_run.md)
