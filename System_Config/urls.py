from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import handler404, handler500, handler400

urlpatterns = [
    path('admin/', admin.site.urls),

    path('taskle/', include("Main.urls")),

]

handler404 = 'Main.views.Error.custom_404'  # 404 エラー用のカスタムビュー
handler500 = 'Main.views.Error.custom_500'  # 500 エラー用のカスタムビュー
handler400 = 'Main.views.Error.custom_400'  # 404 エラー用のカスタムビュー
handler415 = 'Main.views.Error.custom_415'

# 静的ファイル設定（開発環境用）
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
