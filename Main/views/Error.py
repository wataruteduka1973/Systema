from django.shortcuts import render


def custom_404(request):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)


def custom_400(request):
    return render(request, '400.html', status=400)


def custom_415(request):
    return render(request, '415.html', status=415)
