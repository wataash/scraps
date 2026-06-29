# pw_google_photos_html.md — Google フォト DOM 構造リファレンス

[pw_google_photos.py](pw_google_photos.py) が依存している Google フォト Web UI の HTML 構造の記録。
Google が UI を変更してスクリプトが壊れたとき、このファイルと実際の DOM を見比べて修復する。

- 調査日: 2026-06-10、英語 UI、デスクトップ版 <https://photos.google.com/>
- 注意: `tL9Q4c` のような難読化クラス名は Google のビルドごとに変わりうる。**aria-label・role・placeholder・タグ名を一次手がかり、難読化クラス名を補助手がかり**とするのが本スクリプトの方針。
- 例中の ID・ファイル名・地名等はプレースホルダに置き換えてある (`AF1Qip...`, `PersonA`, `CityName` など)。

## ページ種別と URL

| ページ | URL | 使うサブコマンド |
|---|---|---|
| 写真ビュー | `https://photos.google.com/photo/<ID>` | set_descr, get_info, get_info_date, add_to_album |
| 検索結果グリッド | `https://photos.google.com/search/<query>` | get_info_date |
| アルバム一覧 | `https://photos.google.com/albums` | new_shared_album |
| アルバムビュー | `https://photos.google.com/album/<ID>` | new_shared_album |

- `<ID>` は `AF1Qip` で始まる英数字 (`[A-Za-z0-9_-]+`)。
- 検索結果から開いた写真の href は `./search/<base64トークン>/photo/<ID>` 形式になるが、`/photo/<ID>` 部分だけ取り出して `https://photos.google.com/photo/<ID>` に正規化すれば直接開ける (`collect_photo_urls_for_date` の regex `/photo/([A-Za-z0-9_-]+)`)。
- 日付検索は `https://photos.google.com/search/January%202,%202006` のように `<Month D, YYYY>` (英語 UI) のクエリで、その日の写真だけがヒットする。

## 写真ビュー (`/photo/<ID>`)

### 上部ツールバー

`<button>` (一部 `<a>`, `<div role="button">`) に英語の aria-label が付く。クラスは難読化 (`pYTkkf-...`) で当てにならない。

| aria-label | 用途 |
|---|---|
| `Open info` | 情報パネルを開く。`open_info_panel()` が最優先でクリックする |
| `Close info` | 情報パネルを閉じる。**2 要素ある**: パネル内の `<button aria-label="Close info">` と、`<div aria-label="Close info" class="DNAsC ...">`。可視性判定 (`has_visible_info_pane`) の手がかりにも使っている |
| `More options` | メニューを開く。`open_add_to_album_dialog()` が「Add to album」を選ぶのに使う |
| `Share` / `Favorite` / `Move to trash` | 使っていない |
| `Back to photos & videos` | 使っていない |
| `View previous photo` / `View next photo` | `<div role="button">`。使っていないが、日付内の写真を順に辿る代替手段になりうる |

### 情報パネル (右側 360px)

ビューポート右端に幅 360px で出る。コード中の可視判定 `r.right > vw - 420` はこの幅 (360px + 余裕) に由来。

説明 textarea から上への DOM チェーン (2026-06 時点):

```
textarea.tL9Q4c                ← 説明エディタ
└ div.kmqzh                    ← has_visible_info_pane の手がかりの 1 つ
  └ div.qURWqc
    └ div.zE2Vqb
      └ div.ZPTMcc             (w=360, パネル本体)
        └ div.YW656b           (w=360, h=viewport)
          └ c-wiz.WUbige
```

### 説明エディタ (set_descr / get_info の核心)

```html
<textarea jsname="YPqjbf"
          jsaction="change:FDSEXc; focus:Jt1EX; blur:fpfTEe; input:Lg5SV; keydown:Hq2uPe"
          spellcheck="false" autocomplete="off"
          placeholder="Add a description"
          initial-data-value="(現在の説明)"
          class="tL9Q4c"
          aria-label="Description">(現在の説明)</textarea>
```

- 安定した手がかり: `textarea[aria-label="Description"]`、`placeholder="Add a description"`。`get_description_editor()` はこの 2 つを最優先候補にしている。
- `initial-data-value` 属性に編集前の値が入る (現在未使用だが検証の代替手段になる)。
- **非表示の同型 textarea が複数存在する** (隣の写真のプリロード分)。必ず `:visible` で絞ること。
- 値の確定: フォーカスを外す (blur) と保存される。`commit_description()` は Save/Done ボタンを探し、なければ Tab キー。2026-06 時点では明示的な Save ボタンは無く Tab フォールバックが動いている。

### 詳細 (Details) 欄 — 各行に意味的な aria-label がある

行コンテナは `div.R9U8ab` (主要素) / `span.sprMUb` (付随情報)。**重要: 各行には英語の意味的 aria-label が付いており、これが最も頑健な抽出手段** (現在の実装は innerText の行解析だが、壊れたらこちらに乗り換えるとよい):

| aria-label パターン | 例 | 対応する details キー |
|---|---|---|
| `Date taken: <date>` | `Date taken: Jan 2` | date |
| `Time taken: <time>` | `Time taken: Mon, 3:04 PM` | time |
| `GMT+09:00` | (タイムゾーンそのもの) | timezone |
| `Filename: <name>` | `Filename: PXL_20060102_150405000.mp4` | filename |
| `Megapixel: <n>MP` | `Megapixel: 1.4MP` | megapixels |
| `Size: <w> × <h> pixels` | `Size: 1524 × 926 pixels` | dimensions |
| `File size: <size>` | `File size: 78.4 MB` | (backup_status に含まれる) |
| `Learn more about backup quality` | (`<a>`) | quality |

- 今年の写真は日付に年が付かない (`Jan 2`)。過去の年は `Jan 2, 2006` 形式。
- innerText 行解析 (`parse_info_details`) が前提とする行順: 日付 → 時刻 → タイムゾーン → ファイル名 → 画素数 → 解像度 → `Uploaded from ...` → `Backed up (...)` → `... Learn more` → 場所 → `Map data ©<year> Google` → `Terms`。

### 場所

```html
<div jsname="yHbGQd" class="ffq9nc WAICmc GHWQBd" tabindex="0"
     aria-label="Edit location" role="button">
  <dt class="dNjXAc"><svg>...</svg></dt>
  <dd class="rCexAf"><div><div class="R9U8ab">CityName</div></div></dd>
  ...
</div>
```

- 手がかり: `[aria-label="Edit location"]`。inner_text が地名 (`get_visible_location`)。
- 場所未設定の写真にはこの要素ではなく「Add a location」系 UI が出る (その場合 location は null)。

### アルバム / 共有リンク

```html
<a class="rugHuc" href="./share/AF1Qip..." data-shared="true">
  <div class="sZ63vb" style="background-image: url(...)"></div>  <!-- サムネイル -->
  <div class="DgVY7">
    <div class="AJM7gb">Space with PersonA</div>                  <!-- タイトル -->
    <div class="nAfFgf">16 items · Shared · Feb 10 – Apr 25</div> <!-- サマリ -->
  </div>
</a>
```

- 手がかり: `a.rugHuc` (`get_visible_albums`)。href は `./share/<ID>` (共有) または `./album/<ID>` (アルバム)。
- タイトル/サマリは innerText の 1 行目/2 行目以降として取っているので、`AJM7gb`/`nAfFgf` が変わっても動く。
- これも非表示の複製があるため、位置 (`r.x > window.innerWidth - 420`) と可視サイズでフィルタしている。

### 人物 (People) — 未使用

`a.eNIBQd[aria-label="unlabeled person"]` または人物名。情報パネルの People セクション。

### 動画プレイヤー (get_video_duration)

動画写真では YouTube 埋め込み iframe が使われる:

- iframe URL: `https://youtube.googleapis.com/embed/?autohide=1&ps=picasaweb&...` — フレーム検出は URL の `youtube.googleapis.com/embed/` 部分文字列。
- iframe 内: `<span class="ytp-time-duration">5:58</span>` (標準 YouTube プレイヤーのクラス、比較的安定)、`<video class="video-stream html5-main-video">` の `video.duration` プロパティ (秒, float)。
- コントロールはマウスを動かさないと出ない → `page.mouse.move(600, 500)` してから読む。

### 情報パネルのテキスト取得ヒューリスティック (get_visible_info_pane_lines) の実態

現在の JS (`w>300 && h>400 && right>vw-420 && innerText.includes('Details')` で最大面積の div) は、実際には**パネル単体ではなく全画面コンテナ** (例: `div.fzyONc.QtVoBc`, 1920×993) にマッチしている。そのため `pane_lines` には `Share` / `Info` / `Favorite` などツールバーのテキストも混入する。後段の `parse_info_details` が `Details` 行以降だけを見るので実害がない、という構造。修復時は「`Details` を含む最大面積の可視 div」という条件さえ維持すれば多少の混入は許容される。パネルだけに絞りたければ `div.ZPTMcc` (w=360) 相当を探すか、上記の意味的 aria-label に乗り換える。

## アルバム作成フロー (new_shared_album) — 調査日: 2026-06-11

1. アルバム一覧 (`/albums`): 「Create album」ボタン。role=button、accessible name `Create album` で取れる (`click_create_album`)。クリックした時点で**無題のアルバムが作成され** `/album/<ID>` に遷移する。
2. アルバム名入力 (アルバムビュー、編集モード):

```html
<textarea aria-label="Edit album name" placeholder="Add a title"
          class="tL9Q4c CGafTb">(アルバム名)</textarea>
```

   - 手がかり: `textarea[aria-label="Edit album name"]` (`fill_album_title`)。クラス `tL9Q4c` は説明エディタと同じ。
   - **`placeholder="Add a title"` だが aria-label に "title" は含まれない**ことに注意。
3. 上部ツールバー (編集モード): `<button>` の aria-label は `Done` (左上のチェック) / `Share` / `More options` / `Add text` / `Add locations` / `Sort photos`、戻るは `<a aria-label="Back">`。`Done` クリックで編集モード終了 (`click_album_done`)。
4. `Share` クリック (`open_album_share_dialog`) で共有ダイアログが開き、「Create link」ボタン → 確認ダイアログの「Create link」ボタンの2段 (`create_share_link` は最大2回クリック)。
5. 共有 URL は `https://photos.app.goo.gl/<token>` 形式で、ダイアログ内のテキストまたは input value に現れる。`wait_for_share_url` は `document.body.innerText` と全 `input`/`textarea` の value を regex `https://photos\.app\.goo\.gl/[\w-]+` で走査する。

## アルバムへの追加フロー (add_to_album) — 調査日: 2026-06-11

1. 写真ビューの上部ツールバー「More options」(`button[aria-label="More options"]`) をクリックするとメニューが開き、`role=menuitem` の「Add to album」がある (`open_add_to_album_dialog`)。**ツールバーは自動で隠れ、非表示の複製ボタンも存在する**ため、`page.mouse.move()` で表示させてから `:visible` 付きセレクタでクリックする。
2. アルバム選択ダイアログ (`[role="dialog"]`) の上部に検索入力がある:

```html
<input type="text" placeholder="Search albums" class="qdOxv-fmcmS-wGMbrd">  <!-- aria-label は無い -->
```

   入力するとアルバム一覧 (`ul[role="listbox"][aria-label="Album list"]`) が絞り込まれる (`pick_album_in_add_dialog` はスクロールではなくこの検索で目的のアルバムを出す)。ほかに「Clear search」ボタン、所有者フィルタ (`Show all albums` / `Show my albums` / `Show albums shared with me`)、`Sort by` メニューがある。アルバム 1 件 = 1 つの `<li>`:

```html
<li role="option" aria-label="AlbumName · 16 items · Shared" data-id="AF1Qip...">
  ...<span class="aqdrmf-rymPhb-fpDzbe-fmcmS">AlbumName</span>...
</li>
```

   - **クリックは `<li role="option">` に対して行う** (`pick_album_in_add_dialog` は `get_by_role('option', name=<アルバム名>)` を最優先候補にしている。名前テキストの `<span>` をクリックしようとすると li が pointer events を横取りして `intercepts pointer events` でタイムアウトする)。
   - `get_by_role` の name は部分一致なので、aria-label `<アルバム名> · N items · Shared` にアルバム名が含まれていれば当たる (アルバム名の直後に空白が 2 つ入る個体もあるため、完全一致ではなく部分一致が必要)。
   - `data-id` がアルバム ID。
3. クリックすると即座に追加されてダイアログが閉じ、「Added to <album>」トーストが出る。確認ボタンは無い。

## 検索結果グリッド (`/search/<query>`)

写真 1 枚 = 1 つの `<a>`:

```html
<a class="p137Zd" tabindex="0"
   href="./search/<base64トークン>/photo/AF1Qip..."
   aria-label="Video - Landscape - Jan 2, 2006, 3:04:05 PM">
  <div class="RY3tic" style="background-image: url(...)">...</div>
</a>
```

- 手がかり: `a[href*="/photo/"]` (`collect_photo_urls_for_date`)。クラス `p137Zd` には依存していない。
- aria-label 形式: `Photo|Video - Landscape|Portrait - <Mon D, YYYY, H:MM:SS AM/PM>`。現在未使用だが、ページ遷移せずに日付・種別でフィルタする手段になる (メインのタイムライン `photos.google.com/` のグリッドも同形式)。
- グリッドは仮想スクロール。`scrollHeight > clientHeight` な要素は**存在しない** (overflow するスクロールコンテナ方式ではない) ため、`element.scrollTop` 操作は効かない。`page.mouse.wheel()` でホイールイベントを送るのが確実 (現実装)。スクロールで DOM 上の `<a>` が増えていき、増えなくなったら全件読み込み済みと判断する。

## サブコマンド × 依存セレクタ対応表

| 関数 | 依存する DOM | 壊れたときの症状 |
|---|---|---|
| `open_info_panel` | `button[aria-label="Open info"]` ほかフォールバック | `AssertionError: Failed to open Google Photos info panel` |
| `has_visible_info_pane` / `wait_for_info_pane` | `textarea[aria-label="Description"]`, `div.kmqzh`, `[aria-label="Close info"]` | `Info pane did not become visible` |
| `get_description_editor` | `textarea[aria-label="Description"][placeholder="Add a description"]` ほか | `description editor was not found` |
| `fill_description` | textarea (fill) / contenteditable (キーボード) の分岐 | 説明が入力されない |
| `commit_description` | Save/Done ボタン (現在は無い) → Tab フォールバック | `verify_description` の不一致で検出 |
| `get_visible_info_pane_lines` | `Details` を含む右側の大きな div | `info pane text was not found` |
| `parse_info_details` | Details 以降の行順・行書式 (上記) | details のキー欠落・誤割当 (例外にはならない) |
| `get_visible_location` | `[aria-label="Edit location"]` | location が null になる |
| `get_visible_albums` | `a.rugHuc` | albums が `[]` になる |
| `get_video_duration` | iframe URL `youtube.googleapis.com/embed/`, `.ytp-time-duration`, `<video>` | duration が無くなる (例外にはならない) |
| `collect_photo_urls_for_date` | `a[href*="/photo/"]`, 検索 URL 書式, ホイールスクロール | `No photos found for <date>` |
| `click_create_album` | button name `Create album` (/albums) | `"Create album" button was not found` |
| `fill_album_title` | `textarea[aria-label="Edit album name"]` | `Album title input was not found` |
| `click_album_done` | `button[aria-label="Done"]` | `"Done" button was not found` |
| `open_album_share_dialog` | `button[aria-label="Share"]` | `Share button was not found` |
| `create_share_link` / `wait_for_share_url` | button name `Create link` (2段), URL `photos.app.goo.gl` | `Share URL ... was not found` |
| `open_add_to_album_dialog` | `button[aria-label="More options"]`, menuitem `Add to album` | `"More options" button / "Add to album" menu item was not found` |
| `pick_album_in_add_dialog` | `input[placeholder="Search albums"]`, `li[role="option"]` (aria-label にアルバム名) | `"Search albums" input / Album ... was not found in the add-to-album dialog` |
| `verify_albums` | `a.rugHuc` (`get_visible_albums` 経由) | `Failed to add to albums` |

## 修復手順

1. `google-chrome --remote-debugging-port=9222 --user-data-dir=/var/tmp/pw_google_photos/ https://photos.google.com/` でログイン済みブラウザを起動し、壊れたページを開く。
2. 下記スニペットで現在の DOM を採取し、本ファイルの記述と diff を取る:

```python
import json
import playwright.sync_api as sync_api

with sync_api.sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = next(pg for pg in browser.contexts[0].pages if pg.url.startswith('https://photos.google.com/'))
    page.goto('https://photos.google.com/photo/AF1Qip...', wait_until='domcontentloaded')
    page.wait_for_timeout(4000)
    # 可視要素の aria-label 一覧 (ボタン・詳細行の語彙変更を検出)
    print(json.dumps(page.evaluate("""
() => Array.from(document.querySelectorAll('[aria-label]')).filter(e => {
  const r = e.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}).map(e => ({tag: e.tagName.toLowerCase(), role: e.getAttribute('role'),
              ariaLabel: e.getAttribute('aria-label'),
              cls: (e.getAttribute('class') || '').slice(0, 60)}))
"""), ensure_ascii=False, indent=1))
    # 説明 textarea とその祖先チェーン (難読化クラス名の変更を検出)
    print(json.dumps(page.evaluate("""
() => {
  let e = document.querySelector('textarea[aria-label="Description"]');
  const chain = [];
  for (let i = 0; i < 8 && e; i++, e = e.parentElement)
    chain.push({tag: e.tagName.toLowerCase(), cls: e.getAttribute('class')});
  return chain;
}
"""), indent=1))
```

3. 変更点に応じて `pw_google_photos.py` の該当関数 (上の対応表) の候補セレクタリストに新しいものを**先頭に追加**する (旧候補は残してフォールバックにする)。
4. 本ファイルの該当箇所と調査日を更新する。
5. `pw_google_photos.py -h` の epilog にある実行例で動作確認する (set_descr → get_info → get_info_date の順が手早い)。
