# ローカル版で日本語パスワードが認証できなかった問題（2026-11-14）

## 症状

MacのCIA Printローカル版で、参加者パスワード `いんさつ` を入力しても認証できなかった。設定ファイルは正しく、サーバー自体も起動していた。

`POST /api/unlock` に直接リクエストしたところ、HTTP 500 と次のエラーが返った。

```text
comparing strings with non-ASCII characters is not supported
```

## 根本原因

`local_server.py` の `constant_match()` で、`hmac.compare_digest(str(value), str(expected))` にUnicodeの日本語文字列を渡していた。`hmac.compare_digest` が `str` を受け取る場合はASCII文字に制限され、日本語が含まれると例外が発生する。これはパスワード不一致（HTTP 401）ではなく、サーバー内部エラー（HTTP 500）だった。

修正後：

```python
hmac.compare_digest(
    str(value).encode("utf-8"),
    str(expected).encode("utf-8"),
)
```

両方をUTF-8バイト列に揃えて比較することで、日本語パスワードに対応する。英数字の管理画面パスワードも引き続き比較できる。

## 切り分けの記録

1. GitHubの初期値とMacの `local-config.json` を確認：両方とも `いんさつ`。
2. `lsof -nP -iTCP:8765 -sTCP:LISTEN` でPythonが待ち受け中と確認。
3. プロセスの作業ディレクトリが `~/Desktop/cia-print` であることを確認。
4. 再起動しても症状は継続した。
5. ブラウザを経由せず認証APIを直接呼び出してHTTP 500の具体的な例外を取得。
6. 比較時のUTF-8バイト列への変換により、ローカル環境で認証成功を確認。

この問題は、その後に発生した「IPアドレスを取得できませんでした」というネットワーク検出の問題とは別件。認証処理の修正だけでは、テザリング環境のIP表示や端末間通信は改善しない。

## 再発防止

- `tests/test_local_authorization.py` に、日本語の正しいパスワード・誤った日本語パスワード・英数字の管理用パスワード・Unicode比較の回帰テストを追加。
- Python 3.9を含む実行環境でテストする。
- UIの「パスワードが違う」といった表示だけで原因を判断せず、HTTPステータスとサーバー例外を確認する。
- 設定内容が正しいことと、プログラムがその値を正常に処理できることを別々に検証する。

## テスト手順

リポジトリ直下で以下を実行：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

ローカルサーバー起動後、認証APIだけを調べる場合：

```bash
curl -i --max-time 5 -X POST http://127.0.0.1:8765/api/unlock \
  -H 'Content-Type: application/json' \
  -d '{"password":"いんさつ"}'
```

期待値：成功時はHTTP 200と `ok: true`。認証トークンが返るため、外部へログを共有するときにはトークンを伏せる。間違ったパスワードはHTTP 401、プログラム例外はHTTP 500として区別する。

**注意:** 実際の印刷テストは別途必要。認証テストの成功はプリンターの動作を保証しない。
