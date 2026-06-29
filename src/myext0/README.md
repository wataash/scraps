# MyExt0

個人用の VSCode 拡張。

## コマンド

| コマンド | ID | 説明 |
|---|---|---|
| myext0 Hello World | `myext0.helloWorld` | 動作確認用。情報メッセージを表示する |
| myext0 Copy Current Code Block | `myext0.copyCodeBlock` | カーソルがいるフェンスドコードブロックの中身（フェンス行を除く）をクリップボードにコピーする |
| myext0 Set Indentation | `myext0.setIndent` | アクティブエディタのインデント設定（スペース/タブ・サイズ）をキーバインドから直接変更する |

### myext0 Copy Current Code Block

Markdown 内で、カーソルがフェンスドコードブロック（``` または `~~~`、3個以上）の中、または開きフェンス行にある状態で実行すると、ブロックの中身だけをコピーする。フェンス行と言語指定（例 ` ```sh `）は除外される。

例: カーソルが下記ブロック内にある状態で実行すると、`code 1 line 1\ncode 1 line 2` がコピーされる。

````md
```sh
code 1 line 1
code 1 line 2
```
````

制約:

- ネストフェンス（4個 ``` の中に3個など）は厳密には未対応。

### myext0 Set Indentation

アクティブエディタの `TextEditor.options`（そのファイルのインデント設定）を直接変更する。ステータスバーの「Indent Using Spaces / Indent Using Tabs」のクイックピックと同じ効果で、ユーザー設定 (`editor.tabSize` など) は書き換えない。

引数 (`args`) で挙動を指定する:

| キー | 型 | 説明 |
|---|---|---|
| `insertSpaces` | boolean | `true` でスペース、`false` でタブ。省略時は `false` |
| `tabSize` | number | インデント幅。数値のときだけ設定し、省略時は現在値を維持（タブ指定で使う） |

組み込みの `editor.action.indentUsingSpaces` / `indentUsingTabs` は引数を取れずサイズ選択のクイックピックが必ず出る（[vscode#218412](https://github.com/microsoft/vscode/issues/218412) は "not planned"）ため、キーバインドから一発で設定できるよう自作している。

キーバインド例（`keybindings.json`）。`ctrl+m N` でスペース幅N、`ctrl+m ctrl+t ...` でタブ:

```jsonc
{ "key": "ctrl+m 1",              "command": "myext0.setIndent", "when": "editorTextFocus", "args": { "insertSpaces": true,  "tabSize": 1 } }, // スペース 幅1
// ... ctrl+m 2〜9 まで tabSize を変えて同様に定義
{ "key": "ctrl+m ctrl+t ctrl+t", "command": "myext0.setIndent", "when": "editorTextFocus", "args": { "insertSpaces": false, "tabSize": 8 } }, // タブ 幅8
{ "key": "ctrl+m ctrl+t 1",       "command": "myext0.setIndent", "when": "editorTextFocus", "args": { "insertSpaces": false, "tabSize": 1 } }, // タブ 幅1
// ... ctrl+m ctrl+t 2〜9 まで tabSize を変えて同様に定義
```

3連鎖キーチェーン（`ctrl+m ctrl+t N`）は VSCode 1.77+（2023年3月）でサポートされた。

## 開発

```sh
pnpm install
pnpm run compile   # tsc -p ./
pnpm run watch     # ウォッチビルド
pnpm test          # lint + コンパイル + vscode-test
```

F5（Run Extension）で Extension Development Host を起動して動作確認する。
