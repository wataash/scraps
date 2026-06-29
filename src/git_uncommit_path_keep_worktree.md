# git_uncommit_path_keep_worktree.sh

[git_uncommit_path_keep_worktree.sh](git_uncommit_path_keep_worktree.sh)

指定したパスの変更だけを現在の HEAD コミットから取り除きつつ、作業ツリーの内容はそのまま残します。

`git commit --amend` で HEAD を作り直しますが、選んだパスについては親コミットの状態をインデックスに戻すため、amend 後の `git diff` は元の HEAD のパッチ（そのパス分）と一致します。つまりコミットからは外れるが、作業ツリー上の変更としては残ります。

選んだパスが HEAD と同じ内容に作業ツリー上でなっていることが前提です（HEAD との差分があると amend を拒否します）。親コミットに存在しないパスは intent-to-add（`git add -N`）として未追跡相当に戻します。

## 使い方

```sh
git_uncommit_path_keep_worktree.sh <path> [<path> ...]
git_uncommit_path_keep_worktree.sh -- <path> [<path> ...]
```

ディレクトリも指定できます（例: `ps/`）。

## 引数

| 引数 | 説明 |
| --- | --- |
| `<path>` | HEAD コミットから取り除く変更のパス。ファイルでもディレクトリでも可。 |
| `--` | これ以降をオプションではなくパスとして扱う。 |
| `-h, --help` | ヘルプを表示して終了。 |

## エラー

- Git の作業ツリー外で実行した
- HEAD に親が無い（最初のコミットからは取り除けない）
- 選んだパスに HEAD との作業ツリー差分がある（amend を拒否）
- 検証失敗（amend 後の `git diff` が元の HEAD パッチと一致しない）

## 動作の検証

最後に `git diff`（選んだパス）と元の HEAD のパッチを突き合わせ、一致しなければエラー終了します。
