"""アプリケーション層で利用する例外。"""


class ApplicationError(Exception):
    """利用者へ安全に通知できるアプリケーションエラー。"""


class ConfigurationError(ApplicationError):
    """必須設定の不足や不正を表す。"""


class ExternalServiceError(ApplicationError):
    """外部サービスとの通信・応答エラーを表す。"""


class SearchInputError(ApplicationError):
    """外部検索へ渡せない入力を表す。"""


class SearchRateLimitError(ApplicationError):
    """外部検索の実行上限超過を表す。"""

    def __init__(self, retry_after: int):
        super().__init__("検索回数の上限に達しました")
        self.retry_after = retry_after
