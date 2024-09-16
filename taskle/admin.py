from django.contrib import admin

from .models import SelectDestination, scraping

# 表示するデータベースのテーブルを選択


class SelectDestinationAdmin(admin.ModelAdmin):
    list_display = ('Objective', 'Adress', 'Mailtext', 'Subject', 'DeleteFlag')


class scrapingAdmin(admin.ModelAdmin):
    list_display = ('Name', 'Bidding', 'EndPrice', 'StartPrice')


admin.site.register(SelectDestination, SelectDestinationAdmin)
admin.site.register(scraping, scrapingAdmin)
