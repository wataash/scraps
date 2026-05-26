# txp (text private)

テキストから非公開用のマーカーコメントを取り除きます。ファイル引数があれば
そのファイルを読み、なければ stdin を読みます。結果は stdout に出力します。

## 使い方

```bash
txp input.md > public.md
cat input.md | txp > public.md
txp --preserve-plp input.md
txp --help
```

## ビルド

```bash
cargo build --release
mkdir -p ~/d/s/bin
cp target/release/txp ~/d/s/bin/txp
```

`~/d/s/bin/txp` がビルド済みの実行ファイルです。必要なら
`~/d/s/bin/` を `$PATH` に追加して `txp` として呼び出します。

## テスト

```bash
./txp_test.sh
```

Rust の単体テストを実行し、`~/d/s/bin/txp` をビルドします。`c.js` が
見つかる環境では `c.js -q txtPrivate` との互換性も確認します。

## オプション

| オプション | 説明 | デフォルト |
| --- | --- | --- |
