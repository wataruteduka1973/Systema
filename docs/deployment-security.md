# 本番環境のセキュリティ設定

Systemaは環境変数でローカル環境と本番環境を分離します。本番起動前に次を設定してください。

```powershell
$env:SYSTEMA_ENV = "production"
$env:DJANGO_SECRET_KEY = "十分に長いランダムな秘密鍵"
$env:DJANGO_ALLOWED_HOSTS = "example.com,www.example.com"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "https://example.com,https://www.example.com"
$env:EXTERNAL_SEARCH_RATE_LIMIT = "30"
$env:EXTERNAL_SEARCH_RATE_WINDOW_SECONDS = "60"
```

HTTPSをリバースプロキシで終端し、`X-Forwarded-Proto` を信頼できる構成の場合だけ次も設定します。

```powershell
$env:DJANGO_BEHIND_HTTPS_PROXY = "true"
```

信頼できるリバースプロキシが接続元IPを上書きする構成に限り、`EXTERNAL_SEARCH_TRUST_X_FORWARDED_FOR=true` を設定できます。利用者が直接送信した `X-Forwarded-For` を信頼してはいけません。

本番モードではHTTPSリダイレクト、Secure Cookie、HSTSが有効になります。HSTSを有効にする前に、対象ドメインとサブドメインが常にHTTPSで提供されることを確認してください。

秘密鍵をリポジトリ、ログ、画面、サポートメッセージへ記録しないでください。漏えいが疑われる場合は、直ちに新しい値へローテーションしてください。

Linux（Docker Compose）では、これらの値を `.env` に書きます。`scripts/linux/create-env.sh --domain <ドメイン>` が秘密鍵とデータベースのパスワードをランダムに生成し、所有者だけが読めるモード600で作成します。手順は [Linuxでの運用](deployment-linux.md) を参照してください。

デプロイ前診断:

```powershell
python manage.py check --deploy
```
