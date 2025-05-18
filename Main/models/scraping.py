from django.db import models


class scraping(models.Model):
    SearchWord = models.TextField()
    SearchDay = models.TextField()
    Bidding = models.TextField()
    EndPrice = models.IntegerField()
    StartPrice = models.IntegerField()
    Name = models.TextField()
    URL = models.TextField()

    def __str__(self):
        return f"{self.Name} - {self.SearchDay}"

    class Meta:
        verbose_name = "商品詳細"
        verbose_name_plural = "検索結果"
