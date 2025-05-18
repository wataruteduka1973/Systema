from django.contrib import admin
from django.utils.html import format_html
from .models.scraping import scraping
from .models.errorlog import ErrorLog


@admin.register(scraping)
class ScrapingAdmin(admin.ModelAdmin):
    # 一覧画面で表示するフィールド
    list_display = ('Name', 'SearchWord', 'SearchDay',
                    'EndPrice', 'StartPrice', 'Bidding', 'url_link')
    # 検索可能なフィールド
    search_fields = ('Name', 'SearchWord')
    # フィルタリング可能なフィールド
    list_filter = ('SearchDay', 'SearchWord')
    # 一覧画面での並び順
    ordering = ('-SearchDay',)
    # 一ページあたりの表示件数
    list_per_page = 25

    # 編集画面でのフィールド配置
    fields = ('SearchWord', 'SearchDay', 'Name',
              'EndPrice', 'StartPrice', 'Bidding', 'URL')

    def url_link(self, obj):
        return format_html('<a href="{}" target="_blank">URL</a>', obj.URL)

    url_link.short_description = 'リンク'


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ('error_code', 'error_message',
                    'timestamp', 'file_path', 'line_number')
    search_fields = ('error_code', 'error_message')
    list_filter = ('timestamp',)
    ordering = ('-timestamp',)
    list_per_page = 25
