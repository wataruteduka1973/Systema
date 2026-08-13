"""アプリケーション層で利用する例外。"""


class ApplicationError(Exception):
    """利用者へ安全に通知できるアプリケーションエラー。"""


class ConfigurationError(ApplicationError):
    """必須設定の不足や不正を表す。"""


class ExternalServiceError(ApplicationError):
    """外部サービスとの通信・応答エラーを表す。"""
