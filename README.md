# CIA Print

固定資料を1回だけ出力する、イベント参加者向け印刷端末です。iPadからMacを経由し、macOSの印刷機能でEpson EW-M634Tへ送信します。

## 最短起動手順

1. MacとiPadとプリンターを同じネットワークへ接続する。
2. Macの「プリンタとスキャナ」でEW-M634Tを追加する。
3. ターミナルでこのフォルダーを開き、`npm run start:local`を実行する。
4. Macに表示されたIPアドレスを確認し、iPadのSafariで`http://MacのIPアドレス:8000`を開く。
5. 「印刷する」を押す。

現在は`assets/connection-test.pdf`を1部印刷します。本番資料へ変更するときはPDFを配置し、`local-config.json`の`pdf_path`を変更してください。

## 設定

- `printer_name`: `lpstat -p -d`で表示されるプリンター名
- `pdf_path`: 固定印刷物のパス
- `port`: iPadから開くポート番号
- `cooldown_seconds`: 二重印刷を防ぐ待機時間

Epson Connect、Epson Global ID、Vercelの環境変数はこの方式では不要です。Macはスリープさせず、サーバーを起動したままにしてください。
