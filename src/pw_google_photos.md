# pw_google_photos.py

[pw_google_photos.py](pw_google_photos.py)

Playwright で Google フォトの Web UI をブラウザ自動操作し、写真・動画の説明 (description) の更新、情報パネルの内容の JSON 取得、共有アルバムの新規作成、アルバムへの追加を行う CLI ツール。

Google フォトの API では説明の更新ができない(または制限が強い)ため、実際のブラウザを CDP (Chrome DevTools Protocol) 経由で操作することで実現している。

## 使い方

### set_descr — 説明の更新

(nothing to document yet)

### get_info — 情報パネルの JSON 取得

出力例 (整形済み JSON が stdout に出る):

```json
{
  "photo_url": "https://photos.google.com/photo/...",
  "page_url": "https://photos.google.com/photo/...",
  "description": "new description",
  "location": "...",
  "albums": [
    {"title": "アルバム名", "summary": "...", "url": "https://photos.google.com/album/..."}
  ],
  "details": {
    "detail_lines": ["..."],
    "date": "...",
    "time": "...",
    "filename": "IMG_xxxx.jpg",
    "megapixels": "12.2MP",
    "dimensions": "4032 × 3024",
    "backup_status": "Backed up",
    "duration": "0:15",
    "duration_seconds": 15.2
  },
  "pane_lines": ["..."]
}
```

`details` の各キーは情報パネルのテキスト行をヒューリスティックに解析した結果であり、UI の言語・表示内容によっては存在しないキーがある。生の行は `pane_lines` / `details.detail_lines` で確認できる。

#### JSON フィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `photo_url` | string | 入力値。CLI 引数で渡した写真 URL (get_info_date では検索結果から正規化した `https://photos.google.com/photo/<ID>`) |
| `page_url` | string | 情報取得時点でブラウザが実際に表示していた URL (`page.url`)。正常系では `photo_url` と一致する。不一致なら別アカウントへのリダイレクト (`/u/1/...`) や無効 ID などの異常を疑い、その JSON は作り直すのが安全 |
| `description` | string | 説明エディタ (textarea) の現在値。未設定なら `""` |
| `location` | string \| null | 場所 (「Edit location」要素のテキスト)。未設定なら null |
| `albums` | array | この写真が属するアルバム・共有スペースの一覧 (情報パネルの Albums セクション)。属していなければ `[]` |
| `albums[].title` | string \| null | アルバム名 (表示テキストの 1 行目) |
| `albums[].summary` | string \| null | 件数・共有状態・期間など (例: `16 items · Shared · Feb 10 – Apr 25`) |
| `albums[].url` | string \| null | アルバム URL (`https://photos.google.com/album/<ID>` または共有は `.../share/<ID>`) |
| `details` | object | 情報パネル Details 欄の解析結果。以下のキーは該当行が無ければ存在しない |
| `details.detail_lines` | array | Details 見出し以降の生テキスト行。解析がおかしいときはまずこれを見る |
| `details.date` | string | 撮影日 (例: `Jan 2, 2006`)。**今年の写真は年が付かない** (例: `Jan 2`) |
| `details.time` | string | 撮影時刻 (例: `Mon, 3:04 PM`) |
| `details.timezone` | string | タイムゾーン (例: `GMT+09:00`) |
| `details.filename` | string | 元ファイル名 (拡張子で判定) |
| `details.megapixels` | string | 画素数 (例: `12.2MP`) |
| `details.dimensions` | string | 解像度 (例: `4032 × 3024`) |
| `details.upload_source` | string | アップロード元 (例: `Uploaded from Android device`) |
| `details.backup_status` | string | バックアップ状態とファイルサイズ (例: `Backed up (78.4 MB)`) |
| `details.quality` | string | 保存画質 (例: `Storage saver. Learn more`) |
| `details.location` | string | 場所。トップレベル `location` と同じ値。それが取れなかった場合は地図クレジット行の直前の行から推定 |
| `details.duration` | string | 動画の再生時間表示 (例: `0:15`)。動画のみ |
| `details.duration_seconds` | number | 動画の再生時間 (秒, float)。動画のみ。`<video>` 要素の `duration` プロパティ由来 |
| `pane_lines` | array | 情報パネルを含むコンテナの全テキスト行 (Details 以外のセクションやツールバーの文言も混入する)。デバッグ用 |

### get_info_date — 指定日の全写真・動画の情報を一括保存

```sh
pw_google_photos.py get_info_date 2006-01-02 out_dir/
```

指定日 (YYYY-MM-DD) の写真・動画を検索し、それぞれの情報 (get_info と同じ JSON) を `out_dir/<ID>.json` に保存する。`<ID>` は写真 URL `https://photos.google.com/photo/<ID>` の ID 部分。

動作:

1. `https://photos.google.com/search/<Month D, YYYY>` (例: `January 2, 2006`) を開き、グリッドをスクロールしながら写真リンクを収集する (新規リンクが 3 ラウンド連続で増えなくなったら終了)。
2. 各写真ページを開いて情報パネルを取得し、`out_dir/<ID>.json` に書き出す。
3. `<ID>.json` が既に存在する写真はスキップするので、中断しても再実行で続きから処理できる。
4. 取得した情報の日付が指定日と一致しない場合は警告を出す (保存はする)。

### new_shared_album — 共有アルバムの新規作成

```sh
pw_google_photos.py new_shared_album 'album name'
```

新しいアルバムを作成して共有リンクを発行し、その URL を stdout に出力する。

動作:

1. `https://photos.google.com/albums` を開き、「Create album」をクリック (この時点で無題のアルバムが作られ、`/album/<ID>` に遷移する)
2. アルバム名を入力し、左上の Done (チェック) ボタンをクリック
3. 右上の Share ボタン → 「Create link」→ 確認ダイアログの「Create link」で共有リンクを作成
4. 共有 URL (`https://photos.app.goo.gl/...`) を stdout に出力

途中で失敗した場合、無題または共有リンク未発行のアルバムが残ることがある (手動で削除する)。

### add_to_album — 写真/動画をアルバムに追加

```sh
pw_google_photos.py add_to_album 'https://photos.google.com/photo/...' 'album name 1' 'album name 2'
```

写真/動画をアルバム (複数指定可) に追加する。既にそのアルバムにひもづいている場合はスキップする (冪等)。

動作:

1. 写真ページを開き、情報パネルの Albums 欄から現在ひもづいているアルバムを取得
2. 未ひもづきのアルバムごとに: More options → 「Add to album」→ ダイアログの「Search albums」入力にアルバム名を入れて絞り込み、候補から選択
3. 最後に写真ページを開き直し、指定した全アルバムにひもづいたことを検証 (失敗時は `AssertionError`)

アルバムは既存である必要がある (ダイアログ内で見つからなければエラー)。アルバム名はダイアログの aria-label 先頭部分との部分一致で選択するため、別アルバム名の前方部分文字列になっている名前 (例: `foo` と `foo 2`) は誤選択しうる。

## 制限・注意点

- Google フォトの DOM 構造 (クラス名 `kmqzh`, `rugHuc` や aria-label 文言) に依存しているため、UI 変更で壊れる可能性がある。セレクタは英語 UI と日本語 UI の両方を想定した複数候補のフォールバックで頑健性を確保している。依存している DOM 構造の詳細と修復手順は [pw_google_photos_html.md](pw_google_photos_html.md) を参照。
- 既定タイムアウトは 5 秒 (`page.set_default_timeout(5000)`)。要素の可視判定は 1 秒 (`is_visible`)。
- 未ログイン状態では説明エディタが見つからず `AssertionError` になる。エラー時はログイン状態と UI を確認すること。
- `parse_info_details` の地図クレジット判定は `Map data ©2026 Google` という固定文字列に依存しており、年が変わると場所のフォールバック抽出が効かなくなる。
- `get_info_date` の検索クエリは英語形式 (`January 2, 2006`) なので、英語 UI のアカウントを前提とする。
- 今年の写真は情報パネルの日付に年が表示されない (例: `Jun 9`) ため、`details.date` にも年が含まれない。
