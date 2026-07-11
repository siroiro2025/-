# とまりぐるぐる・じどう工房 (tomari-auto)

キャラクターの**一枚絵をアップロードするだけ**で、[tomari-guruguru](https://github.com/rotejin/tomari-guruguru) スタイルのアバター素材を**上半身入り**で自動生成し、そのままブラウザで動かせるアプリです。

- マウス追従（5×5 = 25方向）
- まばたき（目開き / 目閉じ）
- リップシンク（口閉じ / 半開き / 開き — マイク入力 or デモモード）

つまり **5×5方向 × 6表情 = 150フレーム**のスプライトシートを、AIパイプラインが自動で作ってスライスします。元の tomari-guruguru では画像生成〜スライスが手作業でしたが、その工程を丸ごと自動化したものです。

## アーキテクチャ（モデルの役割分担）

コスパに合わせてモデルを使い分けるオーケストレーション構成です。

| 役割 | モデル | 呼び出し回数の目安 |
|---|---|---|
| **オーケストレーター**: 一枚絵の分析、画像生成プロンプトの設計、検品NG時のプロンプト修正 | **Claude Fable 5** (`claude-fable-5`) | 1〜数回（少数の重要な判断のみ） |
| **ワーカー（検品/QC）**: 生成された各シートがグリッド仕様・表情・キャラ一貫性を満たすかチェック | **Claude Haiku 4.5** (`claude-haiku-4-5`) | シートごと（6回〜リトライ分） |
| **画像生成**: スプライトシートの描画 | **ローカル Qwen-Image-Edit 2511**（推奨・無料）または **Gemini** (`gemini-2.5-flash-image`) | シートごと（6回〜リトライ分） |

> Claude は画像の「理解」はできますが「生成」はできないため、描画のみ画像生成バックエンドに委譲しています。指揮系統（分析・プロンプト設計・品質判断のループ）はすべて Claude 側です。
>
> Fable 5 の呼び出しには、安全分類器による誤検知に備えて **Opus 4.8 へのサーバー側フォールバック**をデフォルトで有効にしています（不要なら `src/claude.js` の `betas` / `fallbacks` を外してください）。

### パイプラインの流れ

```
一枚絵アップロード
  └→ ① Fable 5: キャラ分析 + 基準シート用プロンプト設計
      └→ ② Gemini: 基準シート（目開き・口閉じ、5×5方向）生成
          └→ ③ Haiku 4.5: 検品（グリッド/上半身/表情/一貫性）
              ├→ NG: Fable 5 がプロンプトを修正して②へ（上限 MAX_ATTEMPTS 回）
              └→ OK: 残り5表情のシートを基準シート参照で生成（②③を繰り返し）
                  └→ ④ 6シートを25分割ずつスライス → 150フレーム
                      └→ ⑤ ビューアで再生 🎉
```

## セットアップ

必要なもの: Node.js 20.19+、Anthropic API キー、＋画像生成バックエンド（下のどちらか）

```bash
npm install
cp .env.example .env
# .env に ANTHROPIC_API_KEY を記入し、画像生成バックエンドを設定（下記）
npm start
```

### 画像生成バックエンドの選択

**A. ローカル Qwen-Image-Edit 2511（推奨・生成コストゼロ）**

手元のGPUで Qwen-Image-Edit-2511 が動く環境なら、同梱の簡易サーバーを立てるだけです:

```bash
pip install -r tools/requirements.txt
python tools/qwen_server.py --port 8000 --preload
```

`.env` に以下を追加:

```
IMAGE_BACKEND=qwen
QWEN_SERVER_URL=http://localhost:8000
```

- モデルは初回に Hugging Face から `Qwen/Qwen-Image-Edit-2511` を取得します（`QWEN_MODEL` で変更可）。
- VRAM が足りない場合は `QWEN_OFFLOAD=1` で CPU オフロードできます（遅くなります）。
- すでに ComfyUI 等で運用している場合は、`POST /edit`（`{prompt, images:[base64...]}` → `{mimeType, data}`）と同じ形のエンドポイントを用意すればそのまま差し替えられます。

**B. Gemini API**

`.env` に `GEMINI_API_KEY` を記入するだけ（`QWEN_SERVER_URL` 未設定なら自動的に Gemini を使います）。

ブラウザで <http://localhost:3000> を開き、一枚絵をドロップして「アバターを自動生成する」を押すだけです。生成には数分かかります。完成すると `output/<ジョブID>/` にシートとフレームが保存され、ビューアのリンクが表示されます。

## 設定（.env）

| 変数 | 既定値 | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | （必須） | Claude API キー |
| `IMAGE_BACKEND` | 自動判定 | `qwen` / `gemini`。未指定時は `QWEN_SERVER_URL` があれば qwen |
| `QWEN_SERVER_URL` | `http://localhost:8000` | ローカル Qwen サーバーの URL |
| `GEMINI_API_KEY` | — | Gemini バックエンド使用時のみ必須 |
| `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image` | Gemini の画像生成モデル |
| `MAX_ATTEMPTS` | `2` | 1シートあたりの生成リトライ上限（増やすと品質↑コスト↑） |
| `PORT` | `3000` | サーバーポート |

## コストの目安

1回の生成で最低: Fable 5 ×1（分析）+ 画像生成 ×6（シート）+ Haiku ×6（検品）。検品NGが出るとリトライ分だけ呼び出しが増えます。ローカル Qwen バックエンドなら画像生成は無料なので、`MAX_ATTEMPTS` を 3〜4 に上げて品質を優先するのがおすすめです（増えるのは安価な Haiku の検品と、たまの Fable のプロンプト修正だけ）。Gemini 利用時でコストを抑えたいときは `MAX_ATTEMPTS=1` にしてください。

## 既知の制限

- 画像生成モデルの特性上、25セルのグリッドが常に完璧に揃うとは限りません。検品ループで大きな崩れは弾きますが、リトライ上限に達すると警告付きでそのまま採用します（進行状況に ⚠️ 表示）。
- 生成画像の解像度は 1024px 程度のため、1フレームは約200pxです。高解像度が必要な場合はアップスケーラの併用を検討してください。

## クレジット

- 元アプリ・素材フォーマットの発想: [rotejin/tomari-guruguru](https://github.com/rotejin/tomari-guruguru)（MIT License）
- 本リポジトリのコードは新規実装です。生成したキャラクター画像の権利・利用条件は、入力した一枚絵の権利および各AIサービスの利用規約に従ってください。
