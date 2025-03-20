from django.urls import path
from .views import RouteCalculator

urlpatterns = [
    path('calculate/', RouteCalculator.as_view(), name='calculate_route'),
]