from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("taskle/", include("Main.urls")),
]

handler404 = "Main.views.Error.custom_404"
handler500 = "Main.views.Error.custom_500"
handler400 = "Main.views.Error.custom_400"
handler403 = "Main.views.Error.custom_403"

# 静的ファイル設定（開発環境用）
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
