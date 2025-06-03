from django.shortcuts import render


def index(request):
    return render(request, 'StartMenu.html')


def Yahuoku(request):
    return render(request, 'Yahuoku.html')


def Yahuoku_now(request):
    return render(request, 'Yahuoku_now.html')


def Deep_Analysis(request):
    return render(request, 'Deep_Analysis.html')
