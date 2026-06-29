# video_sam2.py

[video_sam2.py](video_sam2.py)

SAM2 (Segment Anything Model 2) を使って、動画内のオブジェクトをマスク画像で指定し、フレーム間で追跡 (セグメンテーションの伝播) を行う CLI ツール。

モデルは [facebook/sam2.1-hiera-tiny](https://huggingface.co/facebook/sam2.1-hiera-tiny) を Hugging Face Hub から自動ダウンロードして使用する (`~/.cache/huggingface/hub/models--facebook--sam2.1-hiera-tiny/` にキャッシュされる)。CUDA が利用可能なら GPU (bfloat16 autocast)、なければ CPU で動作する。

## 必要なもの

- Python パッケージ: `opencv-python`, `numpy`, `torch`, `sam2` ([facebookresearch/sam2](https://github.com/facebookresearch/sam2))
- 入力動画 (mp4 など OpenCV で読めるもの)
- 初期マスク画像: 開始フレームと同じ解像度のグレースケール画像。非ゼロ画素が追跡対象オブジェクトを表す

## 使い方

```bash
python video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask mask.png [--frame_start N] [--frame_end M]
```

`track` サブコマンドのオプション:

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--mask` | ✓ | - | 初期マスク画像のパス。`--frame_start` のフレームに対するマスク |
| `--input` | ✓ | - | 入力動画 |
| `--output_mask_dir` | ✓ | - | マスク画像の出力ディレクトリ (なければ作成される) |
| `--output_preview_dir` | ✓ | - | プレビュー画像の出力ディレクトリ (なければ作成される) |
| `--frame_start` | | `0` | 追跡開始フレーム番号 (このフレームにマスクを与える) |
| `--frame_end` | | 最終フレーム | 追跡終了フレーム番号。`--frame_start` より小さい値を指定すると逆方向 (時間を遡る方向) に追跡する |

### 例

```bash
# フレーム 0 から最後まで追跡
python video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask mask.png

# フレーム 100 から 200 まで追跡
python video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask mask_f100.png --frame_start 100 --frame_end 200

# フレーム 200 から 100 へ逆方向に追跡
python video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask mask_f200.png --frame_start 200 --frame_end 100
```

## plan サブコマンド

手動で作った複数のキーフレームマスクから、動画全体をカバーする `track` コマンド列を生成して標準出力に書き出す。マスクのファイル名 (拡張子を除いた部分) をフレーム番号として解釈する (例: `mask_manual_png/0061.png` → フレーム 61)。

```bash
python video_sam2.py plan --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ mask_manual_png/*.png
# そのまま実行するなら:
python video_sam2.py plan --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ mask_manual_png/*.png | bash
```

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `masks` (位置引数) | ✓ | - | キーフレームマスク PNG (複数可)。ファイル名 = フレーム番号。順不同 (番号順にソートされる) |
| `--input` | ✓ | - | 生成されるコマンドに埋め込む入力動画 |
| `--output_mask_dir` | ✓ | - | 生成されるコマンドに埋め込むマスク出力ディレクトリ |
| `--output_preview_dir` | ✓ | - | 生成されるコマンドに埋め込むプレビュー出力ディレクトリ |

各マスクごとに 2 本のコマンドを生成する:

- **逆方向**: そのフレームから、1 つ前のマスクとの中間フレームまで遡る (先頭のマスクはフレーム 0 まで)
- **順方向**: そのフレームから、次のマスクとの中間フレームまで進む (末尾のマスクは動画の最後まで)

これにより各フレームは最も近いキーフレームマスクから伝播された結果でカバーされる。出力例:

```
time video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask=mask_manual_png/0061.png --frame_start=0061 --frame_end=0000
time video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask=mask_manual_png/0061.png --frame_start=0061 --frame_end=0078
time video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask=mask_manual_png/0095.png --frame_start=0095 --frame_end=0078
time video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask=mask_manual_png/0095.png --frame_start=0095
```

## replan サブコマンド

追跡結果を見て手修正したい区間を標準入力または位置引数で渡し、XCF作成、GIMP起動、手修正PNG抽出、再追跡のコマンド列を生成する。

```bash
printf '0241-0259\n1237-1265\n1288-1464\n1832-1999-2828\n1832-2828,30\n' | python video_sam2.py replan --color 39D3B5 --jpg_dir jpg/ --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/
```

入力は `START-END`、`START-SEED-END`、または `START-END,STEP`。`START-END` の場合は中央値を手修正フレームとして使う。`START-SEED-END` の場合は中央の `SEED` を手修正フレームとして使う。`START-END,STEP` は区間を `STEP` フレームごとに分割し、各チャンクを `START-END` として扱う (例: `1832-2828,30` は `1832-1862`, `1862-1892`, ..., `2822-2828` と等価。最後のチャンクは `END` で切り詰められる)。

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `ranges` (位置引数) | | 標準入力 | `0241-0259`, `1832-1999-2828`, `1832-2828,30` 形式の区間。省略時は標準入力から読む |
| `--input` | ✓ | - | 生成される `track` コマンドに埋め込む入力動画 |
| `--output_mask_dir` | ✓ | - | 生成される `track` コマンドに埋め込むマスク出力ディレクトリ |
| `--output_preview_dir` | ✓ | - | 生成される `track` コマンドに埋め込むプレビュー出力ディレクトリ |
| `--jpg_dir` | ✓ | - | 元フレームJPEGのディレクトリ |
| `--sam2_mask_dir` | | `./sam2_mask` | 既存SAM2マスクPNGのディレクトリ |
| `--mask_manual_xcf_dir` | | `./mask_manual_xcf` | 手修正用XCFの出力ディレクトリ |
| `--mask_manual_png_dir` | | `./mask_manual_png` | 手修正後PNGの出力ディレクトリ |
| `--color` | ✓ | - | `sam2_mask_to_xcf.sh` に渡す色 |
| `--xcf_layer` | | `1` | `magick` で抽出するXCFレイヤー番号 |
| `--no_gui` | | `False` | 生成される `track` コマンドに `--no_gui` を付ける |

出力例:

```bash
sam2_mask_to_xcf.sh 39D3B5 jpg/0250.jpg sam2_mask/0250.png ./mask_manual_xcf/0250.xcf
gimp ./mask_manual_xcf/0250.xcf

magick './mask_manual_xcf/0250.xcf[1]' -alpha extract -negate ./mask_manual_png/0250.png

time video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask=./mask_manual_png/0250.png --frame_start=0250 --frame_end=0241
time video_sam2.py track --input in.mp4 --output_mask_dir sam2_mask/ --output_preview_dir sam2_preview/ --mask=./mask_manual_png/0250.png --frame_start=0250 --frame_end=0259
```

## 出力

フレームごとに 2 種類のファイルを書き出す (`NNNN` は元動画での絶対フレーム番号、ゼロ埋め 4 桁):

- `<output_mask_dir>/NNNN.png` — 二値マスク (対象 = 255、背景 = 0)
- `<output_preview_dir>/NNNN.jpg` — 元フレームにマスクをオレンジ色 (BGR `(0, 200, 255)`、不透明度 45%) で重ねたプレビュー画像

処理中は `preview` ウィンドウに進捗 (フレーム番号入り) がリアルタイム表示され、**Esc キーで中断**できる。

## 処理の流れ

1. 入力動画の `--frame_start`〜`--frame_end` の範囲を JPEG 連番として一時ディレクトリ (`--output_mask_dir` 配下の `sam2_clip_*`、終了時に自動削除) に展開する。SAM2 の video predictor がフレームディレクトリを入力に取るため
2. `SAM2VideoPredictor.init_state()` で推論状態を初期化 (CUDA 時はフレームを CPU にオフロードして VRAM を節約)
3. `add_new_mask()` で開始フレームに初期マスクを `obj_id=1` として登録
4. `propagate_in_video()` でマスクをフレーム間に伝播 (逆方向指定時は `reverse=True`)
5. 各フレームの出力 logits を閾値 0 で二値化し、プレビュー・マスク画像を書き出す

## 制限事項

- 追跡できるオブジェクトは 1 つだけ (`obj_id=1` 固定)
- マスク画像のサイズが開始フレームと一致しないとエラーで停止する
- プレビューウィンドウ表示には GUI 環境が必要。ヘッドレス環境では `--no_gui` を使う (Esc での中断は不可)
