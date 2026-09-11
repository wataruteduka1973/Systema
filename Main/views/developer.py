from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.db import DatabaseError
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from Main.services.admin_monitoring import ERROR_KINDS, LEVELS, monitoring_snapshot


class MonitoringFilterForm(forms.Form):
    days = forms.ChoiceField(
        label="集計期間", choices=(("1", "直近24時間"), ("7", "直近7日"), ("30", "直近30日"))
    )
    level = forms.ChoiceField(
        label="エラーレベル", required=False, choices=(("", "すべて"), *LEVELS.items())
    )
    kind = forms.ChoiceField(
        label="エラー種別", required=False, choices=(("", "すべて"), *ERROR_KINDS.items())
    )


@never_cache
@staff_member_required(login_url="login")
def developer_dashboard(request):
    form = MonitoringFilterForm(
        {
            key: request.GET.get(key, default)
            for key, default in (("days", "7"), ("level", ""), ("kind", ""))
        }
    )
    context = {"filter_form": form, "monitoring_privacy": True}
    valid = form.is_valid()
    if valid:
        try:
            context.update(
                monitoring_snapshot(
                    days=int(form.cleaned_data["days"]),
                    level=form.cleaned_data["level"],
                    kind=form.cleaned_data["kind"],
                )
            )
        except DatabaseError:
            context["aggregate_error"] = True
            return render(request, "developer/dashboard.html", context, status=503)
    return render(request, "developer/dashboard.html", context, status=200 if valid else 400)
