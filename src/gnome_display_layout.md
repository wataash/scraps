# gnome_display_layout.py

[gnome_display_layout.py](gnome_display_layout.py)

このスクリプトは、GNOME Wayland 環境におけるマルチモニターの配置設定を動的かつ一発で適用するためのツールです。同じ型番（シリアル番号違い）のディスプレイを接続し直した際に、配置が初期設定にリセットされてしまう GNOME の制限を解消します。

## 目的 (Purpose)

本ツールは、D-Bus を介して Wayland コンポジター（GNOME Mutter）に直接クエリを送り、現在接続されているモニターの製品モデル（Product）を検出します。
接続されている機器の組み合わせから**シナリオ (どの役割のモニターが揃っているか) を自動判定**し、各シナリオに紐付く variant (レイアウト) を適用します。

### 本ツールの強み
* **シリアル番号を無視**: 異なる個体の同一ディスプレイを接続しても完璧に同じ配置が適用されます。
* **挿す端子を気にしなくて良い**: 製品モデル名で認識するため、HDMI や DP のどの接続ポート（HDMI-1 / HDMI-2 など）に挿しても自動で正しい位置にマッピングされます。
* **第3モニターは wildcard**: 外出先のモニターは型番が変わってもプロファイル追加不要。`etc` ロールとして自動的に取り込まれます。

---

## ハードウェア構成

プロファイルは以下のディスプレイ運用を前提に、**役割 (role)** ベースで設計しています。

| ロール | 製品コード | 役割 | 存在状況 |
| :--- | :--- | :--- | :--- |
| **`pc`** | `0x419f` (eDP-1, Samsung SDC) | PC 内蔵液晶ディスプレイ (常にメイン) | **常に存在** |
| **`portable`** | `DP-FF164S-B` (YCT) | ポータブルディスプレイ | **存在することが多い** (持ち運び用) |
| **`ext4k1440p`** | `EX-LD4K271D` (IO-DATA) | 4K 外部モニター (1440p で運用) | — |
| **`etc`** | *任意* | コワーキングスペース等の据え置き外部モニター | 場所により異なる (機種は様々、wildcard) |

`pc` / `portable` の製品コードはスクリプト内の `ROLE_PRODUCTS` に固定。それ以外に検出されたモニターは自動的に `etc` ロールに割り当てられます。

---

## シナリオとプロファイル一覧

検出された role 集合が一致するシナリオを 1 つ自動選択し、そのシナリオの variant (`-p` で指定、未指定なら `default`) を適用します。

### シナリオ 1: `pc+portable` (2画面)

#### `not_tested_yet.pL` (default)
```text
portable pc
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **portable** | 左 | DP-FF164S-B |
| **pc** | 右 (メイン, scale 1.5) | 0x419f |

#### `not_tested_yet.pR`
```text
pc portable
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **pc** | 左 (メイン, scale 1.5) | 0x419f |
| **portable** | 右 | DP-FF164S-B |

---

### シナリオ 2: `pc+etc` (2画面)

#### `etcU` (default)
```text
etc
pc
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **etc** | 上 | 任意の外部モニター |
| **pc** | 下 (メイン, scale 1.5) | 0x419f |

#### `etcL`
```text
etc pc
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **etc** | 左 | 任意の外部モニター |
| **pc** | 右 (メイン, scale 1.5) | 0x419f |

#### `etcR`
```text
pc etc
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **pc** | 左 (メイン, scale 1.5) | 0x419f |
| **etc** | 右 | 任意の外部モニター |

---

### シナリオ 3: `pc+portable+etc` (3画面)

#### `pL` (default)
```text
         etc
portable pc
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **etc** | 右上 | 任意の外部モニター |
| **portable** | 左下 | DP-FF164S-B |
| **pc** | 右下 (メイン, scale 1.5) | 0x419f |

#### `pR`
```text
etc
pc  portable
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **etc** | 左上 | 任意の外部モニター |
| **pc** | 左下 (メイン, scale 1.5) | 0x419f |
| **portable** | 右下 | DP-FF164S-B |

#### `p_pc_etc`
```text
portable pc etc
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **portable** | 左 | DP-FF164S-B |
| **pc** | 中央 (メイン, scale 1.5) | 0x419f |
| **etc** | 右 | 任意の外部モニター |

#### `etc_pc_p`
```text
etc pc portable
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **etc** | 左 | 任意の外部モニター |
| **pc** | 中央 (メイン, scale 1.5) | 0x419f |
| **portable** | 右 | DP-FF164S-B |

---

### シナリオ 4: `pc+portable+ext4k1440p` (3画面)

EX-LD4K271D を `ext4k1440p` 固定ロールとして検出したときの専用シナリオ。`pc+portable+etc` (wildcard) より優先して一致する。

#### `pL` (default)
```text
       ext4k1440p
portable pc
```
| ロール | 配置 | 製品コード |
| :--- | :--- | :--- |
| **ext4k1440p** | 上 右寄り (mode 強制: 2560x1440) | EX-LD4K271D |
| **portable** | 左下 | DP-FF164S-B |
| **pc** | 右下 (メイン, scale 1.5) | 0x419f |

*※ ext4k1440p はネイティブ 4K より 1440p を優先したいので layout タプル6要素目の `mode_spec` (= `"2560x1440"`) で解像度を強制している*

---

## 使用例 (Usage Example)

### シナリオを自動判定 + 各シナリオの default variant を適用
```bash
~/d/s/gnome_display_layout.py apply
```

### 登録済みシナリオ・variant 一覧を表示
```bash
~/d/s/gnome_display_layout.py list
```

### variant を強制指定して適用
```bash
~/d/s/gnome_display_layout.py apply --profile pR
```

### ドライラン (実際に適用せず、生成される D-Bus コマンドを表示)
```bash
~/d/s/gnome_display_layout.py -n apply -p etcL
```

## オプション (Options)

| オプション | 短縮形 | タイプ | 説明 |
| :--- | :---: | :---: | :--- |
| `--dry_run` | `-n` | フラグ | 実際に設定を反映せず、生成された D-Bus コマンドを標準出力します。 |
| `--help` | `-h` | フラグ | ヘルプメッセージを表示して終了します。 |

### `apply` サブコマンドのオプション

| オプション | 短縮形 | タイプ | 説明 |
| :--- | :---: | :---: | :--- |
| `--profile` | `-p` | 文字列 | 自動判定された **シナリオ内の variant** を明示指定します (例: `pR`)。 |

## AA

```md
- pc: 0x419f
- portable: DP-FF164S-B
- ext4k1440p: EX-LD4K271D (1440p で固定運用)
- etc: その他 (wildcard)

**pc + portable**

`-p not_tested_yet.pL` (default):
portable pc

`-p not_tested_yet.pR`:
pc portable

**pc + etc**
`-p etcU` (default):
etc
pc

`-p etcL`:
etc pc

`-p etcR`:
pc etc

**pc + portable + etc**

`-p pL` (default):
         etc
portable pc

`-p pR`:
etc
pc  portable

`-p p_pc_etc`:
portable pc etc

`-p etc_pc_p`:
etc pc portable

**pc + portable + ext4k1440p**

`-p pL` (default):
       ext4k1440p
portable pc
```
