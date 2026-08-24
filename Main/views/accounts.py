from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST

from Main.forms import AccountCreationForm, InitialAdminCreationForm
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.services.auth_security import (
    AuthRateLimitError,
    check_login_allowed,
    clear_login_failures,
    consume_registration_attempt,
    record_login_failure,
)
from Main.services.ownership import claim_session_data


class SystemaLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        try:
            check_login_allowed(request, request.POST.get("username", ""))
        except AuthRateLimitError as error:
            form = self.get_form()
            form.add_error(None, str(error))
            response = LoginView.form_invalid(self, form)
            response.status_code = 429
            response["Retry-After"] = str(error.retry_after)
            return response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        anonymous_session_key = self.request.session.session_key or ""
        response = super().form_valid(form)
        clear_login_failures(self.request, form.cleaned_data.get("username", ""))
        claim_session_data(self.request.user, anonymous_session_key)
        return response

    def form_invalid(self, form):
        if self.request.method == "POST":
            record_login_failure(self.request, self.request.POST.get("username", ""))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["admin_setup_available"] = (
            settings.ADMIN_SETUP_ENABLED
            and not get_user_model().objects.filter(is_superuser=True).exists()
        )
        return context


class SystemaPasswordChangeView(PasswordChangeView):
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("password_change_done")


@login_required
def profile(request):
    """ログインユーザー本人の利用状況と保存データを表示する。"""
    all_search_runs = SearchRun.objects.filter(user=request.user)
    search_runs = (
        all_search_runs.filter(trigger="manual")
        .annotate(saved_item_count=Count("items"))
        .order_by("-created_at")
    )
    selected_run = None
    selected_run_id = request.GET.get("run")
    if selected_run_id and selected_run_id.isdigit():
        selected_run = search_runs.filter(pk=int(selected_run_id)).first()
    if selected_run is None:
        selected_run = search_runs.first()

    selected_items = selected_run.items.order_by("-id")[:50] if selected_run is not None else []
    watch_items = WatchItem.objects.filter(user=request.user).order_by("-buy_score", "-updated_at")[
        :20
    ]
    keyword_summary = list(
        SearchRun.objects.filter(user=request.user)
        .values("keyword")
        .annotate(search_count=Count("id"))
        .order_by("-search_count", "keyword")[:5]
    )
    saved_searches = SavedSearch.objects.filter(user=request.user)
    selected_saved_search = None
    selected_saved_search_id = request.GET.get("saved_search")
    if selected_saved_search_id and selected_saved_search_id.isdigit():
        selected_saved_search = saved_searches.filter(pk=int(selected_saved_search_id)).first()
    if selected_saved_search is None:
        selected_saved_search = saved_searches.order_by("-last_run_at", "name").first()
    saved_result_run = None
    if selected_saved_search is not None:
        saved_result_run = (
            SearchRun.objects.filter(
                user=request.user,
                saved_search=selected_saved_search,
                search_type=SearchRun.CURRENT,
                succeeded=True,
            )
            .exclude(result_snapshot={})
            .first()
        )
    saved_result = saved_result_run.result_snapshot if saved_result_run else {}
    context = {
        "search_runs": search_runs[:20],
        "selected_run": selected_run,
        "selected_items": selected_items,
        "watch_items": watch_items,
        "search_count": all_search_runs.count(),
        "scraped_item_count": all_search_runs.aggregate(total=Count("items"))["total"],
        "watch_count": WatchItem.objects.filter(user=request.user).count(),
        "keyword_summary": keyword_summary,
        "saved_searches": saved_searches,
        "selected_saved_search": selected_saved_search,
        "saved_result_run": saved_result_run,
        "saved_result": saved_result,
        "saved_result_items": saved_result.get("recommend_items", []),
    }
    return render(request, "accounts/profile.html", context)


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("index")
    form = AccountCreationForm(request.POST or None)
    if request.method == "POST":
        try:
            consume_registration_attempt(request, "signup")
        except AuthRateLimitError as error:
            form.add_error(None, str(error))
            response = render(request, "accounts/signup.html", {"form": form}, status=429)
            response["Retry-After"] = str(error.retry_after)
            return response
    if request.method == "POST" and form.is_valid():
        anonymous_session_key = request.session.session_key or ""
        user = form.save()
        login(request, user)
        claim_session_data(user, anonymous_session_key)
        messages.success(request, "アカウントを作成しました。")
        return redirect("index")
    return render(request, "accounts/signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "ログアウトしました。")
    return redirect("index")


def _superuser_does_not_exist(user):
    return not get_user_model().objects.filter(is_superuser=True).exists()


@user_passes_test(_superuser_does_not_exist, login_url="login")
@require_http_methods(["GET", "POST"])
def admin_setup(request):
    """スーパーユーザーが存在しない場合だけ初回管理者を作成する。"""
    if not settings.ADMIN_SETUP_ENABLED:
        raise Http404
    form = InitialAdminCreationForm(request.POST or None)
    if request.method == "POST":
        try:
            consume_registration_attempt(request, "admin-setup")
        except AuthRateLimitError as error:
            form.add_error(None, str(error))
            response = render(
                request, "accounts/admin_setup.html", {"form": form}, status=429
            )
            response["Retry-After"] = str(error.retry_after)
            return response
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if get_user_model().objects.filter(is_superuser=True).exists():
                messages.error(request, "初回管理者はすでに作成されています。")
                return redirect("login")
            user = form.save()
        anonymous_session_key = request.session.session_key or ""
        login(request, user)
        claim_session_data(user, anonymous_session_key)
        messages.success(request, "初回管理者を作成しました。")
        return redirect("developer_dashboard")
    return render(request, "accounts/admin_setup.html", {"form": form})
