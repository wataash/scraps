#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

cd "$(dirname "$0")"

node_out="${TMPDIR:-/tmp}/txp.node"
rust_out="${TMPDIR:-/tmp}/txp.rust"
node_preserve_out="${TMPDIR:-/tmp}/txp-preserve.node"
rust_preserve_out="${TMPDIR:-/tmp}/txp-preserve.rust"

cargo test
cargo build --release

mkdir -p ../bin
cp target/release/txp ../bin/txp

if command -v c.js >/dev/null 2>&1; then
  c.js -q txtPrivate /home/wsh/qjs/tesjs/s/c.ts > "$node_out"
  ../bin/txp /home/wsh/qjs/tesjs/s/c.ts > "$rust_out"
  cmp "$node_out" "$rust_out"

  c.js -q txtPrivate --preserve-plp /home/wsh/qjs/tesjs/s/c.ts > "$node_preserve_out"
  ../bin/txp --preserve-plp /home/wsh/qjs/tesjs/s/c.ts > "$rust_preserve_out"
  cmp "$node_preserve_out" "$rust_preserve_out"
else
  printf 'skip c.js compatibility check: c.js not found\n' >&2
fi
