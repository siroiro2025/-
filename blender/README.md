# Blender スクリプト置き場

Blender（スクリプト専用版 `bpy`）で背景や人物の `.glb` を作るためのスクリプトです。

## 準備（クラウド環境）

```bash
bash blender/setup_blender.sh
```

`blender-py` というコマンドが使えるようになります（中身は Blender 入りの Python）。

## 初詣の神社シーン

```bash
blender-py blender/scenes/hatsumode_shrine.py --crowd blender/scenes/hatsumode_crowd.json
```

| ファイル (`blender/output/`) | 内容 |
|---|---|
| `hatsumode_shrine_bg.glb` | 背景のみ（人物なし） |
| `hatsumode_shrine_full.glb` | 背景＋人物 |
| `hatsumode_shrine.blend` | Blender で開いて調整する用 |
| `hatsumode_shrine.png` | 完成イメージ |

オプション:
- `--preview` … 小さい画像ですばやく確認（約 1 分半）
- `--cam main|stalls|haiden` … カメラ位置（鳥居ごし / 屋台の列 / 拝殿の近く）
- `--night` … 夜（屋台の明かりが主役。`hatsumode_shrine_night*.png` に出る）
- `--stall-light 30` … 屋台の照明の強さ
- `--count 80` … 人物の総数
- `--seed 5` … 人の並びや服をランダムに変える
- `--no-render` / `--no-export` … 画像だけ・書き出しだけを省く

## 人物（マネキン）の指定

`blender/scenes/hatsumode_crowd.json` に 1 人ずつ書くと、その通りに配置されます。
残りの人数はランダムな冬服の参拝客で埋まります。

```json
{"gender": "female", "outfit": "kimono", "outfit_color": "kimono_red",
 "hair": "bun", "pos": [-0.9, -2.2], "facing": 170}
```

| 項目 | 指定できる値 |
|---|---|
| `gender` | `male` / `female` |
| `outfit` | `down`（ダウン） / `long_coat` / `short_coat` / `kimono`（晴れ着） |
| `outfit_color` ほか色 | `black` `navy` `beige` `pink` `camel` `kimono_red` など、または `#RRGGBB` |
| `bottom` | `pants` / `skirt` |
| `hair` | `short` / `long` / `bob` / `bun` / `bald` |
| `scarf` / `hat` | 色（なしは書かない） |
| `mask` | `true` で白マスク |
| `bag` | `shoulder` / `backpack` |
| `pose` | `stand` / `walk` |
| `height` | 身長 (m) |
| `pos` | 置き場所 `[x, y]`（参道は x=-3〜3、鳥居は y=0、拝殿の石段は y=17.7〜） |
| `facing` | 向き（度）。180 = 拝殿の方、0 = 手前向き |

マネキンの見本は `blender-py blender/scenes/mannequin_lineup.py` で
`output/mannequin_lineup.png` と `output/mannequins.glb` に出ます。

## 屋台の種類

`lib/yatai.py` の `THEMES` に 1 軒ずつ書いてあります。店名・テントの色・幕の色・
屋根の上の看板・のぼり旗・商品の種類（`kind`）を変えられます。

| kind | 商品 |
|---|---|
| `yakisoba` | 鉄板と焼きそば、パック |
| `takoyaki` | たこ焼き器、舟皿 |
| `ringo` / `banana` | りんご飴 / チョコバナナ（串を発泡スチロールに挿す） |
| `castella` | ベビーカステラ・東京ケーキの焼き機と紙袋 |
| `amazake` | 甘酒の寸胴と紙コップ |
| `yakitori` | 炭火の焼き台と串 |
| `wataame` | わたあめ機と吊るした袋 |
| `jaga` | 蒸し器とじゃがいも |
| `omen` | 奥の壁のお面と風船 |

どの屋台にも、ガスボンベ・ポリタンク・クーラーボックス・ブルーシート・
裸電球・蛍光灯・値札がつきます。文字は IPA ゴシック（`/usr/share/fonts`）で書いています。

## ファイル構成

- `lib/sbuild.py` … マテリアル・形を作る共通部品（日本語の文字も）
- `lib/roofs.py` … 反りのある屋根と瓦（丸瓦の列・巴瓦・熨斗瓦の棟）
- `lib/trees.py` … 冬の裸木・常緑広葉樹・杉・植え込み
- `lib/yatai.py` … 屋台
- `lib/mannequin.py` … マネキン生成（色の一覧 `PALETTE` もここ）
- `scenes/hatsumode_shrine.py` … 神社シーン本体
