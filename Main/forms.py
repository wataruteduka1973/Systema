from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class AccountCreationForm(UserCreationForm):
    email = forms.EmailField(label="メールアドレス", required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")


class InitialAdminCreationForm(AccountCreationForm):
    """初回セットアップ専用の管理者作成フォーム。"""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
        return user
