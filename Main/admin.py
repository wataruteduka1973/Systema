from django.contrib import admin
from django.utils.html import format_html

from .models.errorlog import ErrorLog
from .models.scraping import scraping

# スクレイピングモデル


@admin.register(scraping)
class ScrapingAdmin(admin.ModelAdmin):
    list_display = (
        "Name",
        "SearchWord",
        "SearchDay",
        "EndPrice",
        "StartPrice",
        "Bidding",
        "url_link",
    )
    search_fields = ("Name", "SearchWord")
    list_filter = ("SearchDay", "SearchWord")
    ordering = ("-SearchDay",)
    list_per_page = 25
    fields = ("SearchWord", "SearchDay", "Name", "EndPrice", "StartPrice", "Bidding", "URL")

    def url_link(self, obj):
        return format_html('<a href="{}" target="_blank">URL</a>', obj.URL)

    url_link.short_description = "リンク"


# エラーログモデル


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("error_code", "error_message", "timestamp", "file_path", "line_number")
    search_fields = ("error_code", "error_message")
    list_filter = ("timestamp",)
    ordering = ("-timestamp",)
    list_per_page = 25
