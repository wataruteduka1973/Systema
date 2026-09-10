エラーログ設定
======================

HTTP 4xx/5xx、ブラウザーのJavaScriptエラー種別、管理コマンドの失敗を、
リクエスト内容や認証情報を保存せず記録します。HTTP応答の ``X-Request-ID``
を使ってサーバーログとDBの ``ErrorLog`` を照合できます。

ファイルログは既定10 MiB、5世代でローテーションします。
``LOG_MAX_BYTES`` と ``LOG_BACKUP_COUNT`` で変更できます。DBログは既定90日で、
``ERROR_LOG_RETENTION_DAYS`` で変更できます。手動削除確認には
``python manage.py prune_error_logs`` を使用します。

.. automodule:: Main.middleware.error_logging_middleware
    :members:
    :undoc-members:
    :show-inheritance:
