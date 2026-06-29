# jsonc_record_grep.sh

[jsonc_record_grep.sh](jsonc_record_grep.sh)

JSONC 配列（VSCode の `keybindings.json` など）から、**1エントリ（レコード）全体**を
単位にして grep するツール。

## 動機

VSCode のキーバインドは 1 エントリが複数行にまたがる:

```jsonc
{ "key": "ctrl+pagedown",         "command": "workbench.action.terminal.focusNext",
                                     "when": "terminalFocus && ..." }, // Focus Next Terminal Group
```

`rg group` のような行単位の grep だと、`group` を含む `"when":` 行だけしか出ず、
`{ "key": ... }` の頭が欠ける。このツールはレコード全体を出力するので、
元の整形と末尾の `// コメント` がそのまま残る。

`jq` でも `select` で抽出できるが、コメントと桁揃えは失われる（純 JSON に正規化される）。
**見た目とコメントを保ったまま絞り込みたいとき**に使う。

## 使い方

```
jsonc_record_grep.sh [-i] [-r RECORD_START_RE] PATTERN [FILE...]
```

- `PATTERN` … AWK の拡張正規表現（ERE）。レコード内のどこかの行にマッチすれば、
  そのレコード全体を出力する。
- `FILE` … 省略時は stdin を読む。複数指定可（ファイル境界でレコードはリセット）。

### オプション

- `-i`, `--ignore-case` … 大文字小文字を無視。
- `-r`, `--record-start REGEX` … レコード開始行の判定パターンを上書き。
  既定は `^[[:space:]]*[{]`（行頭、インデント可の `{`）。
- `-h`, `--help` … ヘルプ。

## レコードの区切り

- **開始**: `--record-start`（既定 `^[[:space:]]*[{]`）にマッチする行。
- **終了**: 次の開始行、または `]` で始まる行の直前まで。
- **レコード外の行**（配列開始の `[`、先頭コメント、配列末尾以降に列挙される
  `// - command // ...` のような未割り当てコマンド一覧など）は、レコードに
  連結せず**その行単独**で扱う。PATTERN にマッチすればその1行だけを出力し、
  マッチしなければ無視する。

## 例

```sh
# group を含むエントリを丸ごと（大小無視）
jsonc_record_grep.sh -i group keybindings.jsonc

# command が terminal.focus で始まるもの
jsonc_record_grep.sh 'terminal\.focus' keybindings.jsonc

# パイプでも
cat keybindings.jsonc | jsonc_record_grep.sh -i group
```

## 制限

- レコード単位の **テキスト** grep であって JSON パースはしない。`args` などの
  ネストした `{` が行頭（インデントあり）に来る形式では、`--record-start` の
  既定パターンが誤って新レコード開始とみなす可能性がある。その場合は
  `-r '^[{]'`（インデントなしの行頭 `{` のみ）などで調整する。
- マッチ判定は行単位。複数行にまたがる正規表現マッチには非対応。
