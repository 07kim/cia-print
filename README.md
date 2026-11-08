# CIA Print

固定資料を1回だけ出力する、イベント参加者向け印刷端末です。Epson EW-M634Tとの接続確認用管理画面を含みます。

## 現在の範囲

- 固定資料のプレビュー
- 固定された印刷条件の表示
- 送信中、印刷中、完了の画面遷移
- 処理中の連打防止
- `?fail=1` によるエラー表示確認
- `/admin` のプリンター管理画面
- Epson Connect API 2.0の機器認証、状態確認、固定A4テスト印刷

参加者画面はまだ試作動作です。実機への送信は管理画面のテスト印刷だけに限定しています。

## 初回設定

1. EW-M634TをEpson Connectへ登録する。
2. Epson Connect APIサイトでアプリを作成する。
3. Redirect URIに `https://print-kappa-one.vercel.app/api/epson/callback` を登録する。
4. `.env.example` に記載した環境変数をVercelへ設定する。
5. 再デプロイ後、`/admin` からEpsonで認証する。

認証情報はGitHubへ保存しません。詳しい境界は `docs/ARCHITECTURE.md` を参照してください。
