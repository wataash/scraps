# claude_session_tree

[claude_session_tree.py](claude_session_tree.py)

Claude Code のセッション履歴をツリー表示する CLI。

`~/.claude/projects/<エンコード済みパス>/<session-id>.jsonl` を読み、resume によって枝分かれしたセッション群の関係を復元し、ユーザープロンプトのツリーとして出力する。

## 使い方

```sh
python claude_session_tree.py show [TARGET] [--max-prompt N] [--color {auto,always,never}]
```

```sh
# 全プロジェクトを mtime 昇順で表示
python claude_session_tree.py show

# 特定プロジェクトのみ
python claude_session_tree.py show ~/path/to/project

# session-id プレフィックスで絞り込み (祖先 + 子孫のみ)
python claude_session_tree.py show 01e93746
```

## オプション

| オプション | 説明 |
|---|---|
| `TARGET` (位置引数) | 省略時: 全プロジェクト。実パス / エンコード済みディレクトリ / session-id プレフィックス (16進4文字以上) を渡せる。 |
| `--max-prompt N` | 各プロンプトを N 文字で切り詰める (デフォルト 60)。 |
| `--color {auto,always,never}` | ANSI カラー。`auto` は stdout が tty のときのみ色付け。 |

## 出力例

```
directory: /home/user/project  (/home/user/.claude/projects/-home-user-project)
- abcdef12-... (Session title) prompt1 | prompt2 | prompt3
  - ~9876fedc-... prompt4 (未ラベル行)
    - 11112222-... (Forked session) prompt5 | prompt6
```

行の構成: `- <sid> [(aiTitle)] <prompt1> | <prompt2> | ...`

- **シアン** の `<sid>`: そのチェーン末尾が `<sid>.jsonl` の最終プロンプト。`/resume <sid>` で正確にこの状態へ戻る。`aiTitle` が併記される。
- **グレー** の `~<sid>`: 行末プロンプトはどの session の leaf でもない。`~<sid>` はその prompt を**途中で経由する** session の id (`/resume <sid>` するとその session に戻る — 終点は別の行)。
- 線形チェーン (子1つ) は ` | ` で連結し、分岐点で子ツリーへ折る。

## 仕組み

1. プロジェクトディレクトリ配下の全 `*.jsonl` を走査。
2. 各レコードの `uuid`/`parentUuid` を全て記録 (アシスタント/ツール結果も含む)。
3. ユーザープロンプトのみ抽出 (`tool_result`, `<command-*>`, `<system-reminder>`, sidechain などはスキップ)。
4. 各プロンプトの「実効的な親プロンプト」を、`parentUuid` チェーンを上に辿り最も近いプロンプト祖先で決定。複数 jsonl が UUID プレフィックスを共有しているケースが共通祖先で繋がる。
5. ルートから DFS 描画。線形チェーンは ` | ` で1行に圧縮、分岐点で改行。

### session-id 絞り込み

`TARGET` に session-id プレフィックスを渡すと:

1. 全プロジェクトを横断検索しマッチした session を1つ確定 (複数マッチ時はエラーで候補一覧)。
2. その session の **leaf プロンプト** を起点に、祖先方向は直系のみ・子孫方向は全 fork を残す。
3. 兄弟ノードを削除しても、**元のツリーで fork 点だった祖先は独立ノードとして残す** (filter でチェーンが繋がり分岐の痕跡が消えるのを防ぐ)。

## エンコード規則 (注意)

実パスの `/` と `.` を `-` に置換する Claude 本体の保存規則は衝突しうる。例えば `/home/user/qrs/tesrs` と `/home/user/qrs-tesrs` は同じ `~/.claude/projects/-home-user-qrs-tesrs` に保存される。
