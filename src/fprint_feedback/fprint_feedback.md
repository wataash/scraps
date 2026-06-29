# fprint_feedback

[fprint_feedback.py](fprint_feedback.py)

指紋認証(`fprintd`)のタッチに気付けるよう、認証結果を **LED 点滅** と **画面四隅の点滅**(`corner-blink` GNOME 拡張)でフィードバックする。

目的: ログインや `sudo` で指紋を何度もタッチする際、「いま 1 回タッチが受理された」のを体感できるようにし、余剰タッチがマルウェアの権限昇格に流用されるのを抑止する。

## 仕組み

`fprintd` の `VerifyStatus` はブロードキャスト D-Bus signal なので、`BecomeMonitor`(eavesdrop, 要特権)を使わず、通常の match rule (`gdbus monitor`) で誰でも受信できる。これを購読し、結果に応じてフィードバックする。

| 結果 | 判定 | 色 (四隅) | interval | duration |
|------|------|-----------|----------|----------|
| `verify-match` | 成功 | lime | 200ms | 1200ms |
| `verify-no-match` | 失敗 | red | 100ms | 500ms |
| その他 (retry 等) | 無視 | — | — | — |

LED は単色ハードウェアなので色は付かない(点滅タイミングのみ)。点滅後は元の明るさに戻す。

責務を 2 プロセスに分離(同じ signal を各々独立購読、セッション間 IPC 不要):

- **`led` サブコマンド** … LED の `/sys/class/leds/*/brightness` を書く。**root 権限が必要**。system service として常駐(GDM ログイン画面でも効く)。
- **`corner` サブコマンド** … `corner-blink` 拡張の `flash-trigger` を GSettings 経由で bump(同時に `size` を 64px に設定し、四隅の点を見やすくする)。**ユーザ権限**。user service として常駐(ロック画面では効くが GDM greeter では効かない)。

対象 LED: `platform::micmute`, `platform::mute`, `tpacpi::lid_logo_dot`, `tpacpi::power`(存在しないものはスキップ)。

## 使い方

```sh
# セットアップ確認 (センサーに触れずに 1 回ずつ発火)
sudo /usr/local/bin/fprint_feedback led    --self_test
python fprint_feedback.py             corner --self_test

# 何が実行されるか確認するだけ (実行しない)
python fprint_feedback.py corner --self_test --dry_run
```

## オプション

| オプション | 意味 | 既定 |
|------------|------|------|
| `led` / `corner` | サブコマンド(必須) | — |
| `-q`, `--quiet` | ログ抑制(サブコマンドより前に置く); 既定:debug, `-q`:info, `-qq`:warning, `-qqq`:error | debug |
| `-n`, `--dry_run` | 実行せずコマンド/動作を表示 | off |
| `--self_test` | 成功+失敗を 1 回ずつ発火して終了 | off |

## インストール

### 1. corner-blink 拡張に flash 機能 (済) を反映

`flash-color` / `flash-interval` / `flash-duration` / `flash-trigger` キーを追加済み。スキーマ再コンパイル + (Wayland では) **ログアウト→ログイン**で `extension.js` を反映する。

```sh
glib-compile-schemas ~/.local/share/gnome-shell/extensions/corner-blink@local/schemas/
# ログアウト→ログイン後:
gnome-extensions enable corner-blink@local
```

### 2. install

```sh
sudo z_install ~/d/s/fprint_feedback/fprint_feedback.py /usr/local/bin/fprint_feedback
```

### 3. service を配置・有効化

```sh
# system service (LED, root)
sudo cp ~/d/s/fprint_feedback/fprint-led.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fprint-led.service

# user service (corner-blink, wsh)
cp ~/d/s/fprint_feedback/fprint-corner.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fprint-corner.service
```

### 4. 動作確認

```sh
sudo systemctl status fprint-led.service
systemctl --user status fprint-corner.service
journalctl -u fprint-led.service -f          # 指紋タッチで VerifyStatus ログが出る
```

## 注意・既知の制約

- LED feedback は system service なので GDM ログイン画面でも効く。corner-blink は user session 内なのでロック画面では効くが GDM greeter では効かない。
- 指紋イベント(`VerifyStatus`)は **system バスのブロードキャストでグローバル**。どのターミナル/セッションで `sudo` してもイベント自体は 1 回流れるだけ。フィードバック先は「LED=システムに 1 個の `led` デーモン(常に点滅)」「画面=`corner` デーモンが書く session バス=そのデーモンが居るセッション」で決まる。つまり入れ子 gnome-shell (`dbus-run-session --devkit`) を起動しても、その中で `corner` を起動しない限り devkit 画面は fprint で点滅しない(LED は system service なので常に点滅する)。
- 対象 LED の `trigger` は現状すべて `none` のため、点滅↔復元はクリーン。トリガが有効な LED では復元後に kernel が再上書きする可能性がある。
- `gdbus monitor` は AddMatch ベースで eavesdrop 特権不要。`dbus-monitor` の `BecomeMonitor` は AccessDenied になるので使わない。
