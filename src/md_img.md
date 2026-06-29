# md_img.py

[md_img.py](md_img.py)

Markdown ファイルを、埋め込まれたローカル画像ごと移動／リネームするスクリプト。

`mv SRC DST` は次を行う:

1. `SRC` の Markdown を `DST` へ移動する。
2. `SRC` 内の各画像参照 `![alt](link)` のうち**ローカルファイル**を指すものを、
   `DST` と同じディレクトリへ `<DST の stem>.<画像ファイル名>` という名前で移動する。
   例: `DST` が `renamed.md` で画像が `image.png` なら `renamed.image.png`。
3. 移動後の Markdown 内のリンクを新しいファイル名へ書き換える。
4. `--root` 以下の全ファイルから `SRC` の**パス文字列**への参照を探し、`DST` のパスへ置換する
   （`--no-path-rewrite` で無効化）。絶対パス形式と `~/` 形式の両方を置換するので、
   `file:///home/wsh/...` のような URI 内の参照も対象になる。

URL (`http://`, `https://`, `data:` 等) やアンカー (`#...`) の画像リンクは対象外（そのまま残す）。

`normalize_image_names FILE` は `mv FILE FILE` 相当を**その場で**行う:
Markdown 自体は移動せず、`FILE` 内の各ローカル画像を同じディレクトリの
`<FILE の stem>.<画像ファイル名>` という名前へリネームし、リンクを書き換える。
例: `note.md` の `image.png` → `note.image.png`。
冪等で、既に `<FILE の stem>.` で始まる画像はそのまま残す（再実行しても二重に前置されない）。
パスは変わらないので他ファイルのパス参照の書き換えは行わない。安全チェックは `mv` と同じ
（画像が見つからない／移動先が既に存在する／他の `.md` が同じ画像を参照、でエラー終了）。

`img_mv SRC DST` は**画像ファイル**を `SRC` から `DST` へ移動／リネームし、
`--md_scan_dir` 以下の `.md` の中で `SRC` を指すローカル画像リンクを `DST` へ書き換える:

1. 画像 `SRC` を `DST` へ移動する。
2. `--md_scan_dir` 以下の各 `.md` の `![alt](link)` のうち、解決すると `SRC` の実体パスに
   一致するものを `DST` への参照へ書き換える。相対リンクはその `.md` のディレクトリからの
   相対パスへ、絶対リンクは `DST` の絶対パスへ書き換える（リンクの形式を保つ）。

`mv` / `normalize_image_names` が「Markdown を起点に画像を動かす」のに対し、`img_mv` は
**画像を起点に** Markdown 側のリンクを追随させる（逆向き）。URL・アンカーのリンクは対象外。

## 安全チェック（いずれかに該当するとエラーで終了し、何も移動しない）

`mv` / `normalize_image_names`:


- `SRC` が存在しない。
- `DST` が既に存在する。
- `DST` の親ディレクトリが存在しない。
- `SRC` が参照する画像ファイルが見つからない。
- 移動先の画像ファイル (`<DST stem>.<name>`) が既に存在する。
- 同じ画像ファイルを **`SRC` 以外の `.md` ファイル**も参照している。
  - 参照は各ファイルの位置からの相対パスとして**解決して実体パスで比較**する。
    したがって、別ディレクトリの `.md` が偶然同じ文字列のリンク（例 `image.png`）を
    持っていても、それが別の実ファイルを指すならエラーにはならない。
  - スキャン範囲は `--root`（既定: `SRC` の git リポジトリルート、無ければ `SRC` のディレクトリ）。

`img_mv`:

- `SRC`（画像）が存在しない。
- `DST` が既に存在する。
- `DST` の親ディレクトリが存在しない。

## 使い方

```bash
md_img.py mv input.md ../dst/renamed.md
md_img.py mv -n input.md ../dst/renamed.md      # dry-run: コマンドを印刷するだけ
md_img.py mv --root ~/notes input.md sub/renamed.md
md_img.py normalize_image_names input.md        # input.md の画像を input.<name> へその場でリネーム
md_img.py normalize_image_names -n input.md     # dry-run
md_img.py img_mv old.png new.png                # 画像をリネームし .md のリンクを追随
md_img.py img_mv -n --md_scan_dir ~/d old.png new.png  # dry-run
```

`-n`/`--dry_run` 指定時は、実行する `mv` / `sed` コマンドを標準出力にコピー&ペースト可能な形で印刷するだけで、ファイルは一切変更しない。非 dry-run 時は各コマンドを `logger.info` で出してから実行する。

## オプション

| オプション | 説明 |
| --- | --- |
| `-n`, `--dry_run` | コマンドを実行せず印刷するだけ。 |
| `--no-path-rewrite` | `SRC` のパスへの参照を他ファイルで置換しない（`mv` のみ）。 |
| `--root` | 他ファイルからの参照（画像・パス両方）を探すスキャンルート (既定: `SRC` の git ルート、無ければ `SRC` のディレクトリ)。`mv` / `normalize_image_names`。 |
| `--md_scan_dir` | `SRC`（画像）を参照する `.md` を探すスキャンルート (既定: `SRC` の git ルート、無ければ `SRC` のディレクトリ)。`img_mv` のみ。 |

## 出力例（dry-run）

```text
mv input.md ../dst/renamed.md
mv image.png ../dst/renamed.image.png
mv image-1.png ../dst/renamed.image-1.png
sed -i -e 's#\](image\.png)#](renamed.image.png)#g' ../dst/renamed.md
sed -i -e 's#\](image-1\.png)#](renamed.image-1.png)#g' ../dst/renamed.md
sed -i -e 's#/home/me/notes/misc/note\.md#/home/me/notes/dst/renamed.md#g' index.md
sed -i -e 's#~/notes/misc/note\.md#~/notes/dst/renamed.md#g' other.md
```

## テスト

テストは `md_img.py` 内に同居（pytest）。

```bash
pytest -v --doctest-modules ~/d/s/md_img.py
```
