from django.shortcuts import render


def custom_error(request, exception=None, status=500):
    """
    すべてのエラーで共通のエラーページを表示
    """

    context = {
        "status_code": status,
        "message": None,
    }
    return render(request, "errors.html", context=context, status=status)


def custom_404(request, exception):
    return custom_error(request, exception, status=404)


def custom_500(request):
    return custom_error(request, status=500)


def custom_400(request, exception):
    return custom_error(request, exception, status=400)


def custom_403(request, exception):
    return custom_error(request, exception, status=403)
