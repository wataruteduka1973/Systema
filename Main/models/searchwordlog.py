from django.conf import settings
from django.db import models


class searchwordlog(models.Model):
    """
    検索ワード履歴モデルs
    Attributes:
        word (str): 検索ワード
        searched_at (datetime): 検索日時
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="search_word_logs",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    word = models.CharField(max_length=255, db_index=True)
    searched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.word

    class Meta:
        verbose_name = "検索ワード履歴"
        verbose_name_plural = "検索ワード履歴"
