# br.py

`pnpm`'s `minimumReleaseAge` for Homebrew formulae: install a formula only if
its latest version has been published on `homebrew-core` for at least N hours
(default 168h = 1 week). Acts as a small supply-chain safety net against a
freshly compromised formula bump.

## How it determines "release age"

1. Fetches `https://formulae.brew.sh/api/formula/<pkg>.json` to learn the
   formula file path (e.g. `Formula/j/jq.rb`).
2. Queries the GitHub API for the latest commit touching that file on
   `Homebrew/homebrew-core`.
3. Compares the commit timestamp against `--min_age_hours`.

Both requests are unauthenticated. Heavy use may hit the GitHub anonymous rate
limit (60 req/h per IP).

Only formulae are supported (no casks).

## Usage

```
br.py [-n] install [--min_age_hours H] PKG
br.py [-n] upgrade [--min_age_hours H]
```

`install`: if the formula's latest commit is older than the threshold, runs
`brew install PKG`. Otherwise prints an error and exits with status 1.

`upgrade`: runs `brew outdated --json=v2 --formula`, filters to formulae whose
latest commit is older than the threshold, and runs `brew upgrade --formula`
on that subset (a single batched invocation). Pinned formulae are skipped.

### Examples

```
br.py install jq
br.py install --min_age_hours 24 jq
br.py -n install jq         # print the brew command, do not execute
br.py upgrade
br.py -n upgrade --min_age_hours 24
```

## Options

| Option                  | Description                                                        |
| ----------------------- | ------------------------------------------------------------------ |
| `-n`, `--dry_run`       | Print the `brew install` command instead of executing it.          |
| `--min_age_hours HOURS` | Minimum hours since the last commit to the formula. Default `168` (1 week). |
