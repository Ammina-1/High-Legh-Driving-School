from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('index.html', views.home),
    path('about/', views.about, name='about'),
    path('prices/', views.prices, name='prices'),
    path('booking/', views.booking, name='booking'),
    path('about.html', views.about),
    path('prices.html', views.prices),
    path('booking.html', views.booking),
]
