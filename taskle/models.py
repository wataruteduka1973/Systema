from django.db import models

# メールアドレス系（再利用）


class SelectDestination(models.Model):
    Adress = models.TextField()
    Mailtext = models.TextField()
    Objective = models.TextField()
    Subject = models.TextField()
    Todays = models.TextField()
    DeleteFlag = models.TextField()
# スクレイピングする際にデータベースに情報を入力する


class scraping(models.Model):
    SearchWord = models.TextField()
    SearchDay = models.TextField()
    Bidding = models.TextField()
    EndPrice = models.IntegerField()
    StartPrice = models.IntegerField()
    Name = models.TextField()
    URL = models.TextField()
