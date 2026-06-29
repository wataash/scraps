# pw_bike.py

[pw_bike.py](pw_bike.py)

Fill the docomo-cycle "contact" form for a bike that could not be returned. Connects to an already-running Chromium via CDP (`--remote-debugging-port=...`) and opens a new tab.

## Prerequisites

```sh
pip install -U playwright
playwright install
google-chrome --remote-debugging-port=9222 --user-data-dir=/var/tmp/chrome.pw/
```

## Usage

```sh
pw_bike.py -h
pw_bike.py --date=2026-05-27 --id=TYO12345 \
           --name=YourName --email=you@example.com \
           --user_id=yourid --phone=000-0000-0000
```

## Options

| Option           | Required | Default                   | Notes                                       |
|------------------|----------|---------------------------|---------------------------------------------|
| `--connect_url`  | no       | `http://localhost:9222`   | CDP endpoint of the already-running Chrome. |
| `--date`         | yes      |                           | `YYYY-MM-DD` (ご利用開始日)                |
| `--id`           | yes      |                           | bike id, e.g. `TYO12345`                    |
| `--name`         | yes      |                           | お名前                                       |
| `--email`        | yes      |                           | メールアドレス                               |
| `--user_id`      | yes      |                           | ユーザID                                     |
| `--phone`        | yes      |                           | 登録/連絡先 電話番号                         |
| `--body`         | no       | (Japanese default)        | お問い合わせ本文                             |
| `--pause`        | no       | off                       | Call `page.pause()` before filling.         |
