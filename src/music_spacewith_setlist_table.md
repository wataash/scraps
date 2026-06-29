# music_spacewith_setlist_table

[music_spacewith_setlist_table.py](music_spacewith_setlist_table.py)

バンドセッションのセットリスト(markdown の表、1行1曲、`| length | entry | photos_url | yt_len | yt_url | parts` の6カラム、parts は `楽器:名前` トークンの列挙)を、列揃えされた markdown の表に変換する。

入力形式:

```
| length | entry | photos_url | yt_len | yt_url | parts
|---|---|---|---|---|---
| 4:18 | Colorado Bulldog / Mr. Big | https://photos.google.com/photo/xxxxxxxx | 0:04:19 | https://youtu.be/xxxxxxxx | vo:PersonA gt:PersonB ba:メンバーC dr:メンバーD
| 5:20 | Carry On/Angra | | | | vo:PersonE gt:PersonB gt:メンバーF ba:メンバーC dr:PersonG
| | (songs) | | | |
```

- 最初の非空行はヘッダ行としてスキップする。`-`・`|`・`:`・空白のみの行(区切り行)もスキップする。
- 各データ行は先頭の `|` を除いて `|` 区切りでちょうど6カラム。それ以外はエラー(exit 1)。
- `length` は曲の長さ `分:秒`(例 `4:18`)。空欄可。形式違反はエラー。
- `photos_url` は写真URL。空欄可。空白を含むとエラー。出力では `key` の右の `photos_url` 列に入る。
- `yt_len` は YouTube 動画の長さ `時:分:秒`(例 `0:04:19`)。空欄可。形式違反はエラー。
- `yt_url` は YouTube URL。空欄可。空白を含むとエラー。
- `parts` の楽器は `vo gt ba dr key` の順で並んでいること。各楽器は省略可・繰り返し可(ツインギター等)。順序違反や未知の楽器はエラー(exit 1)。
- 名前に空白は使えない(トークンは空白区切りのため)。
- 各楽器の列数は、入力中の最大繰り返し数に合わせて増える(各楽器最低1列)。
- 空行はスキップする。
- セルは表示幅(全角文字は幅2)でパディングするので、端末上でも表が揃う。

## 使い方

### md: 整列した markdown の表を出力

```bash
music_spacewith_setlist_table.py md --photos_json_dir=photos_json/ < setlist.md
```

`--photos_json_dir=DIR`(必須)は `DIR/*.json`(`"photo_url"` と `"details"."duration"` を持つ JSON)から動画の長さを引いて、`photos_url` の左の `photos_len` 列に入れる。`photo_url` キーなし・該当 URL の JSON なしの場合は警告を出してスキップ(セルは空欄)。

`length` と `photos_len` が両方あるとき、`length > photos_len`、または差が1秒より大きい場合はエラー(exit 1)。`length` と `yt_len` についても同様。

出力:

```
| length | entry                      | vo      | gt      | gt        | ba        | dr        | key | photos_len | photos_url                               | yt_len  | yt_url                    |
|--------|----------------------------|---------|---------|-----------|-----------|-----------|-----|------------|------------------------------------------|---------|---------------------------|
| 4:18   | Colorado Bulldog / Mr. Big | PersonA | PersonB |           | メンバーC | メンバーD |     | 4:19       | https://photos.google.com/photo/xxxxxxxx | 0:04:19 | https://youtu.be/xxxxxxxx |
| 5:20   | Carry On/Angra             | PersonE | PersonB | メンバーF | メンバーC | PersonG   |     |            |                                          |         |                           |
|        | (songs)                    |         |         |           |           |           |     |            |                                          |         |                           |
```

### gen_photos_update_cmds: Google Photos の説明欄・アルバムを更新するコマンド列を出力

```bash
music_spacewith_setlist_table.py gen_photos_update_cmds --photos_json_dir=photos_json/ --shared_album_map=albums.tsv --connect_url=http://localhost:59222 --title='{yt_url}{NL}2026-06-09 Tue {entry}' --setlist_md=setlist.md
```

セットリストは stdin ではなく `--setlist_md=FILE`(必須)から読む。`photos_url` がある行ごとに、次の3コマンドを stdout に出力する(実行はしない)。コマンド名はパディングされ、後続の引数が縦に揃う。

1. `pw_google_photos.py set_descr` — 説明欄を `--title` テンプレートの内容に更新
2. `pw_google_photos.py add_to_album` — メンバーに対応する共有アルバムに追加(対応するメンバーがいない行では出力されない)
3. `pw_google_photos.py get_info` — 更新後のメタデータ JSON を取り直す(`--photos_json_dir` の `<photo_id>.json` にリダイレクト)

`--shared_album_map=FILE`(必須)はヘッダ行付き TSV `shared_album_url<TAB>band_name<TAB>shared_album_name<TAB>message_via`。各行のメンバー名(`band_name`)を `shared_album_name` に変換し、メンバーの登場順(重複は除去)で add_to_album の引数にする。TSV にないメンバー名は警告を出してスキップする(同名の警告は1回だけ)。

`--title=TEMPLATE` は説明欄のテンプレート。`{length}` `{entry}` `{photos_url}` `{yt_len}` `{yt_url}` `{parts}` `{NL}`(改行)が置換される。未知の placeholder はエラー(exit 1)。改行を含む文字列は `"$(printf "%s\n" ...)"` の形で出力される(`$(...)` が末尾の改行を削るので各行が改行区切りになる)。

出力例:

```
pw_google_photos.py set_descr    --connect_url=http://localhost:59222 --connect_use_tab_url_start=https://photos.google.com/ https://photos.google.com/photo/xxxxxxxx "$(printf "%s\n" https://youtu.be/xxxxxxxx '2026-06-09 Tue Colorado Bulldog / Mr. Big')"
pw_google_photos.py add_to_album --connect_url=http://localhost:59222 --connect_use_tab_url_start=https://photos.google.com/ https://photos.google.com/photo/xxxxxxxx 'Spacewith PersonAさん' 'Spacewith PersonBさん'
pw_google_photos.py get_info     --connect_url=http://localhost:59222 --connect_use_tab_url_start=https://photos.google.com/ https://photos.google.com/photo/xxxxxxxx > photos_json/xxxxxxxx.json
```

### messages: 共有アルバムごとのメッセージ(YouTube 動画一覧)を出力

```bash
music_spacewith_setlist_table.py messages --shared_album_map=albums.tsv --setlist_md=setlist.md
```

`--shared_album_map` の TSV の行(アルバム)ごとに、そのメンバー(`band_name`)が出演していて `yt_url` がある曲を集め、「`# アルバム名 | message_via` 見出し・共有 URL・`yt_url entry` 行の列挙・`（非公開アップロードです）`」のブロックを空行区切りで stdout に出力する。曲が1つもないアルバムは出力されない。アルバムの順序は TSV の行順。

出力例:

```
# Spacewith PersonAさん | LINE
https://photos.app.goo.gl/xxxxxxxx
https://youtu.be/xxxxxxxx Colorado Bulldog / Mr. Big
（非公開アップロードです）

# Spacewith PersonBさん | instagram
https://photos.app.goo.gl/xxxxxxxx
https://youtu.be/xxxxxxxx Colorado Bulldog / Mr. Big
（非公開アップロードです）
```

### gen_yt_update_cmds: YouTube 動画のタイトル・説明欄を更新するコマンド列を出力

```bash
music_spacewith_setlist_table.py gen_yt_update_cmds --title='2026-06-09 Tue {entry}' --desc='2026-06-09 Tue session{NL}{entry}{NL}{parts}' < setlist.md
```

`yt_url` がある行ごとに `yt_.py set_meta` コマンドを stdout に出力する(実行はしない)。video id は `yt_url`(`https://youtu.be/<id>` または `v=<id>`)から取り出す。取り出せない場合はエラー(exit 1)。

`--title=TEMPLATE`(タイトル)と `--desc=TEMPLATE`(説明欄)の placeholder は gen_photos_update_cmds の `--title` と同じ。`{parts}` は `vo:PersonA gt:PersonB ...` のような members 列の内容に置換される。

出力例:

```
yt_.py set_meta --video_id=xxxxxxxx --title='2026-06-09 Tue Colorado Bulldog / Mr. Big' --desc="$(printf "%s\n" '2026-06-09 Tue session' 'Colorado Bulldog / Mr. Big' 'vo:PersonA gt:PersonB ba:メンバーC dr:メンバーD')"
```

## オプション

| コマンド / オプション   | 説明                                                |
|-------------------------|-----------------------------------------------------|
| `md`                    | stdin からセットリストを読み、markdown の表を stdout に出力 |
| `gen_photos_update_cmds` | `--setlist_md` からセットリストを読み、`pw_google_photos.py` のコマンド列を stdout に出力 |
| `messages`              | `--setlist_md` からセットリストを読み、共有アルバムごとのメッセージ(YouTube 動画一覧)を stdout に出力 |
| `gen_yt_update_cmds`    | stdin からセットリストを読み、`yt_.py set_meta` のコマンド列を stdout に出力 |
| `--photos_json_dir=DIR` | (md / gen_photos_update_cmds 必須)`DIR/*.json` から動画の長さを引いて `photos_len` 列に入れる。gen_photos_update_cmds では get_info の出力先にもなる |
| `--shared_album_map=FILE` | (gen_photos_update_cmds / messages 必須)ヘッダ行付き TSV `shared_album_url<TAB>band_name<TAB>shared_album_name<TAB>message_via` |
| `--connect_url=URL`     | (gen_photos_update_cmds 必須)`pw_google_photos.py --connect_url` に渡す |
| `--connect_use_tab_url_start=URL_PREFIX` | (gen_photos_update_cmds)`pw_google_photos.py --connect_use_tab_url_start` に渡す(デフォルト `https://photos.google.com/`) |
| `--title=TEMPLATE`      | (gen_photos_update_cmds / gen_yt_update_cmds 必須)説明欄 / タイトルのテンプレート(`{entry}` `{NL}` 等を置換) |
| `--desc=TEMPLATE`       | (gen_yt_update_cmds 必須)説明欄のテンプレート(placeholder は `--title` と同じ) |
| `--setlist_md=FILE`     | (gen_photos_update_cmds / messages 必須)セットリストファイル(markdown の表) |
| `-h`, `--help`          | ヘルプを表示                                        |
