# CIA Print アーキテクチャ

## 境界

- 参加者画面は固定資料の印刷操作だけを提供する。
- `/admin` はプリンター設定、接続確認、テスト印刷だけを提供する。
- Epson Connectの認証と印刷ジョブはVercel Functionsから実行する。
- API Key、Client ID、Client Secret、管理PIN、暗号化鍵はVercelの環境変数だけに置く。
- OAuthの機器トークンは暗号化したHttpOnly Cookieに保持する。GitHubや画面へ出さない。
- 固定印刷物はリポジトリ内のPDFとして管理する。

## Epson Connect API 2.0

1. 管理者がEpson Connectの機器認証を開始する。
2. Epsonの認証画面で使用プリンターを選択する。
3. コールバックで取得したトークンを管理端末の暗号化Cookieへ保存する。
4. 管理画面はDevice Information APIでオンライン状態を確認する。
5. テスト印刷はジョブ作成、PDFアップロード、印刷実行の順で処理する。

## 制約

- インターネット接続が必要。
- トークンを保持する管理端末のブラウザを変更した場合は再認証する。
- 参加者向け本番印刷への接続は、実機テストが成功した後の別フェーズとする。

