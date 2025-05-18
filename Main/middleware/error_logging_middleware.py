import logging
import traceback
from django.http import HttpResponseServerError
from ..models.errorlog import ErrorLog


class ErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # ログ設定
        self.logger = logging.getLogger('error_logger')

    def __call__(self, request):
        response = self.get_response(request)
        # レスポンスのステータスコードがエラー（400番台、500番台）をチェック
        if 400 <= response.status_code < 600:
            error_code = response.status_code
            error_message = f"HTTP {error_code} Error: {response.reason_phrase}"
            file_path = request.path  # リクエストパスを記録
            line_number = None  # HTTPエラーでは行番号なし

            # ログに記録
            self.logger.error(
                f"Error Code: {error_code}, Message: {error_message}, Path: {file_path}")

            # データベースに保存
            ErrorLog.objects.create(
                error_code=str(error_code),
                error_message=error_message,
                file_path=file_path,
                line_number=line_number
            )
        return response

    def process_exception(self, request, exception):
        # 例外が発生したときの処理
        tb = traceback.format_exc()
        error_code = getattr(exception, 'status_code', 500)  # デフォルトは500
        error_message = str(exception)
        file_path = traceback.extract_tb(exception.__traceback__)[-1].filename
        line_number = traceback.extract_tb(exception.__traceback__)[-1].lineno

        # ログに記録
        self.logger.error(
            f"Error Code: {error_code}, Message: {error_message}, Traceback: {tb}")

        # データベースに保存
        ErrorLog.objects.create(
            error_code=str(error_code),
            error_message=error_message,
            file_path=file_path,
            line_number=line_number
        )

        return HttpResponseServerError("An error occurred. Check the admin panel for details.")
