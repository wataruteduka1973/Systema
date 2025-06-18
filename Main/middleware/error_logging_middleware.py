import logging
import traceback
from ..models.errorlog import ErrorLog


class ErrorLoggingMiddleware:
    """
    アプリケーションのエラーと例外を記録するミドルウェアです。
    このクラスは HTTP エラー (4xx と 5xx のステータスコード) と例外をキャプチャ、
    ログの記録とデータベースの保存を行います。
    """

    def __init__(self, get_response):
        """
        初期化メソッド。ミドルウェアのインスタンスを初期化します。
        """
        self.get_response = get_response
        self.logger = logging.getLogger('error_logger')

    def __call__(self, request):
        """
        リクエストを処理し、HTTP エラーが発生した場合にエラーログを記録します。
        """
        response = self.get_response(request)
        if 400 <= response.status_code < 600:
            error_code = response.status_code
            error_message = f"HTTP {error_code} Error: {response.reason_phrase}"
            file_path = request.path
            line_number = None

            self.logger.error(
                f"Error Code: {error_code}, Message: {error_message}, Path: {file_path}")

            ErrorLog.objects.create(
                error_code=str(error_code),
                error_message=error_message,
                file_path=file_path,
                line_number=line_number
            )
        return response

    def process_exception(self, request, exception):
        """
        例外が発生した場合に呼び出され、エラーログを記録します。
        """
        tb = traceback.format_exc()
        error_code = getattr(exception, 'status_code', 500)
        error_message = str(exception)
        file_path = traceback.extract_tb(exception.__traceback__)[-1].filename
        line_number = traceback.extract_tb(exception.__traceback__)[-1].lineno
        self.logger.error(
            f"Error Code: {error_code}, Message: {error_message}, Traceback: {tb}")

        ErrorLog.objects.create(
            error_code=str(error_code),
            error_message=error_message,
            file_path=file_path,
            line_number=line_number
        )
        return None
