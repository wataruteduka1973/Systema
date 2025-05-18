from django.db import models


class ErrorLog(models.Model):
    error_code = models.CharField(max_length=50, help_text="エラーコード")
    error_message = models.TextField(help_text="エラーメッセージ")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="発生時刻")
    file_path = models.CharField(
        max_length=255, blank=True, help_text="発生ファイルパス")
    line_number = models.IntegerField(null=True, blank=True, help_text="発生行番号")

    def __str__(self):
        return f"{self.error_code} - {self.timestamp}"

    class Meta:
        verbose_name = "エラーログ"
        verbose_name_plural = "エラーログ一覧"
