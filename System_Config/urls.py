from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import PasswordChangeDoneView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from Main.views.accounts import (
    SystemaLoginView,
    SystemaPasswordChangeView,
    admin_setup,
    logout_view,
    profile,
    signup,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", SystemaLoginView.as_view(), name="login"),
    path("accounts/signup/", signup, name="signup"),
    path("accounts/logout/", logout_view, name="logout"),
    path("accounts/profile/", profile, name="profile"),
    path(
        "accounts/password-change/",
        SystemaPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
        name="password_change_done",
    ),
    path("accounts/admin-setup/", admin_setup, name="admin_setup"),
    path("taskle/", include("Main.urls")),
]

handler404 = "Main.views.Error.custom_404"
handler500 = "Main.views.Error.custom_500"
handler400 = "Main.views.Error.custom_400"
handler403 = "Main.views.Error.custom_403"

# 静的ファイル設定（開発環境用）
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
