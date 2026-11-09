# CIA Print

iPadのブラウザから、印刷設定やOSの印刷ダイアログを表示せず、Mac経由で固定PDFを1部印刷するイベント用ローカルシステムです。

## 画面

- 参加者: `http://MacのIPアドレス:8765/`
- 管理者: `http://MacのIPアドレス:8765/admin/`
- 初期参加者パスワード: `PRINT`
- 初期管理者PIN: `6340`

初期値は管理画面で必ず変更してください。実際の印刷PDFは未確定のため、現在は接続確認票を使います。

## 起動

Finderから`CIA Printを起動.command`をダブルクリックすると起動できます。

ターミナルから起動する場合：

```sh
npm run start:local
```

起動後、ターミナルにiPad用の参加者URLと管理画面URLが自動表示されます。表示されたURLをそのままiPadのSafariへ入力してください。

イベント当日の完全な導入・接続・復旧手順は [運用セットアップ完全マニュアル](./docs/OPERATIONS_MANUAL.md) を参照してください。

## 主な設定

`local-config.json`に保存されます。通常はファイルを直接編集せず、管理画面を使用します。

- `printer_name`: macOSに登録されたプリンター名
- `pdf_path`: 固定PDF
- `cooldown_seconds`: 二重印刷防止時間
- `reset_seconds`: 受付完了後、ロック画面へ戻るまでの時間
- `access_password`: 参加者パスワード
- `admin_pin`: 管理画面PIN

Epson Connect、Epson Global ID、Vercelは不要です。iPad、Mac、プリンターを同じローカルネットワークに接続して使用します。
