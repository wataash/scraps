# bl

[bl](bl)

Small helper for scaffolding a Next.js page in a personal blog repo.

## Purpose

`bl new <name>` creates a new `app/<name>/` directory under the blog repo with two files:

- `app/<name>/page.tsx` — a thin wrapper that imports and renders the sibling MDX
- `app/<name>/page_.mdx` — the page content stub

Each file embeds cross-links (file:// URL to the other file, plus the dev URL `http://localhost:3000/<name>`) so the pair is easy to navigate from an editor.

## Usage

```
bl new jazz
bl new jazz --blog_dir ~/blog
bl -n new jazz
```

## Options

| Option              | Description                                                     |
| ------------------- | --------------------------------------------------------------- |
| `-n`, `--dry_run`   | Print the actions that would be taken; do not write any files. |
| `--blog_dir PATH`   | Blog repo root. Default: `~/blog`.                              |

### `new` subcommand

| Argument | Description                          |
| -------- | ------------------------------------ |
| `name`   | Page name (becomes `app/<name>/`).   |

## Behavior

- Creates `<blog_dir>/app/<name>/` if missing.
- Refuses to overwrite if `page.tsx` or `page_.mdx` already exists.

## 関連ドキュメント (`~/blog/`)

- [~/blog/AGENTS.md](file:///home/wsh/blog2/AGENTS.md) — リポジトリ全体のエージェント向けガイド
- [~/blog/docs/page-format.md](file:///home/wsh/blog2/docs/page-format.md) — `page.tsx` + `page_.mdx` の標準フォーマット (このツールが生成するもの)
- [~/blog/docs/ui-spec.md](file:///home/wsh/blog2/docs/ui-spec.md) — テーマスイッチャの UI 仕様
