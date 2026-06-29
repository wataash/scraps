# vscode_keybindings_annotate

[vscode_keybindings_annotate.py](vscode_keybindings_annotate.py)

VS Code の「Default Keyboard Shortcuts (JSON)」ダンプの各エントリ末尾に、コマンドの
human-readable な Command Title を `// Category: Title` 形式のコメントとして追記する CLI。
配列内のキーバインドエントリに加え、末尾の
「Here are other available commands:」ブロック(`// - <id>` 形式)の各行にも
`// - <id> // Category: Title` の形で追記する。再実行しても二重には付かない(冪等)。

タイトルは **実行中の VS Code から DevTools プロトコル経由で抽出**する(`dump-titles`)。
キーバインドエディタ(`Ctrl+K Ctrl+S`)の表示と一致し、`Show Search` のような実行時生成タイトルも取れる。

## dump-titles の仕組み

VS Code のコマンドタイトルはレンダラ内のレジストリ(`MenuRegistry` / エディタアクション)が持つが、
バンドル済みで DevTools コンソールからは到達できない。そこで:

1. `code --remote-debugging-port=… --user-data-dir=<temp> --extensions-dir ~/.vscode/extensions` で
   別インスタンスを起動(設定は汚さず、拡張のコマンドも拾う)。
2. CDP で `MenuRegistry.addCommand` / `EditorContributionRegistry.getEditorActions` に
   **停止しない条件付きブレークポイント**(`globalThis.__mr=this,false` 等)を仕掛け、`this`(レジストリ実体)を
   globalThis へ退避。
3. ウィンドウをリロードして登録を再実行させ、グローバルスコープからタイトルを読み出して JSON 化。
   キーバインドエディタと同じ優先順で合成する: エディタアクションのラベル <
   `MenuRegistry.getMenuItems(CommandPalette)` のメニュー項目タイトル < `MenuRegistry.getCommands()` の
   コマンドタイトル(後者ほど優先)。

バンドルは minify されるがメソッド名は保持されるため、`addCommand(a){return this._commands.set(a.id,a)…}`
等の文字列をアンカーにブレークポイント位置(行・列)を算出する(VS Code のバージョンが変わっても追従)。

### 限界

- 起動した VS Code に登録されていないコマンド(未インストール拡張のコマンド等)は取得できない。
  キーバインドダンプと同じ VS Code バージョン・拡張構成で実行するのが望ましい。
- `cursorDown` / `list.focusDown` / `quickInput.*` などタイトルを持たない core/widget コマンドは
  そもそもタイトルが無いので未注釈のまま(これはキーバインドエディタでも同じ)。

## 使い方

```bash
# 1) 実行中相当の VS Code からタイトルを抽出(VS Code ウィンドウが一瞬開く)。JSON は stdout
vscode_keybindings_annotate.py dump-titles > titles.json

# 2) そのタイトルでダンプを注釈。元ファイルは直接編集せず別ファイルへ出力する運用を推奨
vscode_keybindings_annotate.py annotate --titles titles.json keybindings_default.jsonc > keybindings_default_annotated.jsonc
```

`keybindings_default.jsonc` は、コマンドパレットの
`Preferences: Open Default Keyboard Shortcuts (JSON)` で開いて保存したファイル。

依存: `dump-titles` は `websocket-client`(`pip install websocket-client`)が必要。VS Code は
インストール済みの `code` を使う(apt 等の追加は不要)。

## オプション

### dump-titles

JSON は stdout に出力する(ログは stderr)。

| オプション | 説明 |
| --- | --- |
| `--code` | 起動する VS Code 実行ファイル(既定 `code`) |
| `--port` | Chromium remote-debugging ポート(既定 `9222`) |
| `--extensions_dir` | 読み込む拡張ディレクトリ(既定 `~/.vscode/extensions`) |
| `-n`, `--dry_run` | VS Code を起動せず起動コマンドだけ表示 |

### annotate

| オプション | 説明 |
| --- | --- |
| `keybindings_json` | 注釈対象の default keybindings JSON(位置引数、必須) |
| `--titles` | `dump-titles` が出力した `command id -> title` JSON(必須) |
| `-i`, `--in_place` | 標準出力ではなく入力ファイルを書き換える(通常は使わず `>` で別ファイルへ) |
