from django.db import models


class searchwordlog(models.Model):
    word = models.CharField(max_length=255, db_index=True)
    searched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.word

    class Meta:
        verbose_name = "検索ワード履歴"
        verbose_name_plural = "検索ワード履歴"
