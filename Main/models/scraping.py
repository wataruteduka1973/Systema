from django.db import models


class scraping(models.Model):
    """
    相場のデータを格納するテーブル
    このモデルは、相場のデータを格納するために使用されます。
    各商品は、検索ワード、検索日、入札数、終了価格、開始価格、
    商品名、URLを含みます。
    """

    SearchWord = models.TextField(help_text="検索ワード")
    SearchDay = models.TextField(help_text="検索日")
    Bidding = models.TextField(help_text="入札数")
    EndPrice = models.IntegerField(help_text="終了価格")
    StartPrice = models.IntegerField(help_text="開始価格")
    Name = models.TextField(help_text="商品名")
    URL = models.TextField(help_text="URL")

    def __str__(self) -> str:
        return f"{self.Name} - {self.SearchDay}"

    class Meta:
        verbose_name = "商品詳細"
        verbose_name_plural = "検索結果"
