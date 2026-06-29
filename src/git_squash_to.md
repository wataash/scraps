# git_squash_to.sh

[git_squash_to.sh](git_squash_to.sh)

`<revision>..HEAD` を1つのコミットに squash (fixup) して `<revision>` の位置にまとめます。

まとめたコミットのツリーは HEAD のまま（内容は変わらない）で、author（名前・メール・author date）と commit log は `<revision>` のものを再利用します。committer は通常どおり現在のユーザー/時刻です。

`git reset --soft` でブランチの先頭だけを動かすため、作業ツリーとインデックス（ステージ済み/未ステージの変更）はそのまま残ります。

## 使い方

```sh
git_squash_to.sh HEAD~     # HEAD~ と HEAD を1つにまとめる
git_squash_to.sh HEAD~3    # HEAD~3 HEAD~2 HEAD~1 HEAD を1つにまとめる
git_squash_to.sh <revision>
```

## 引数

| 引数 | 説明 |
| --- | --- |
| `<revision>` | squash 先のコミット。`<revision>..HEAD` がこのコミットにまとめられる。author date と commit log はこのコミットのものを使う。 |
| `-h, --help` | ヘルプを表示して終了。 |

## エラー

- Git の作業ツリー外で実行した
- `<revision>` が無効
- `<revision>` が HEAD と同一（squash 対象なし）
- `<revision>` が HEAD の祖先でない

いずれもコミットを書き換えずに終了します。
