from django.shortcuts import render

def home(request):
    return render(request, 'website/index.html')


def about(request):
    return render(request, 'website/about.html')


def prices(request):
    return render(request, 'website/prices.html')


def booking(request):
    return render(request, 'website/booking.html')
