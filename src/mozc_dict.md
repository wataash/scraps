# mozc_dict.py

[mozc_dict.py](mozc_dict.py)

mozc のユーザー辞書 (`~/.config/mozc/user_dictionary.db`) を CLI から編集する。
公式には GUI (`/usr/lib/mozc/mozc_tool --mode=dictionary_tool`) しかないため、
protobuf ファイルを直接読み書きする（依存: Python 標準ライブラリのみ）。

スキーマは [user_dictionary_storage.proto](https://github.com/google/mozc/blob/master/src/protocol/user_dictionary_storage.proto) 準拠。
書き込み時は mozc 本体と同じロックファイル (`.user_dictionary.db.lock`) を flock し、
`user_dictionary.db.bak` にバックアップを取ってからアトミックに置き換える。

登録後は mozc_server が辞書を読み直すよう `--reload`（または `reload` サブコマンド）で
`pkill -x mozc_server` する。mozc_server は次回入力時に自動で再起動する。

## Usage

```console
$ python mozc_dict.py add ふぁぶる Fable --pos 固有名詞 --comment "Claude model" --reload
$ python mozc_dict.py import words.tsv --reload   # よみ<TAB>単語[<TAB>品詞[<TAB>コメント]]
$ python mozc_dict.py list
ふぁぶる	Fable	固有名詞	Claude model
$ python mozc_dict.py remove ふぁぶる --reload
$ python mozc_dict.py dicts
User Dictionary 1	1 entries	id=16147832300347159723
```

## Subcommands

| subcommand | description |
|---|---|
| `dicts` | 辞書一覧（名前・語数・id） |
| `list [--dict NAME]` | エントリを TSV で出力（よみ 単語 品詞 コメント） |
| `add よみ 単語 [--pos 品詞] [--comment C] [--dict NAME] [--reload]` | 1語登録（品詞デフォルト: 名詞） |
| `import TSV [--dict NAME] [--reload]` | TSV 一括登録（`-` で stdin、`#` 行と空行は無視） |
| `remove よみ [単語] [--dict NAME] [--reload]` | よみ（+単語）が一致するエントリを削除 |
| `reload` | `pkill -x mozc_server`（次回入力時に辞書再読込） |

## Options

| option | description |
|---|---|
| `-q` / `-qq` / `-qqq` | ログを info / warning / error に抑制 |
| `-n`, `--dry_run` | reload で実行するコマンドを表示するのみ |
| `--db PATH` | 辞書ファイル（デフォルト: `~/.config/mozc/user_dictionary.db`） |

`--pos` は日本語名（名詞, 固有名詞, 人名, 姓, 名, 短縮よみ, サジェストのみ, 抑制単語, …）
または enum 名（NOUN, PROPER_NOUN, …）。一覧は proto の `PosType` を参照
（エラーメッセージにも全一覧が出る）。

## Notes

- GUI の辞書ツールを開いたまま書き込むとロックエラーになる（仕様どおり）。
- フォーマットは mozc のバージョン間で保証されないが、フィールドは 2013 年頃から安定している
  （動作確認: mozc 2.29.5160.102, Ubuntu）。未知のフィールドは保持して書き戻す。
