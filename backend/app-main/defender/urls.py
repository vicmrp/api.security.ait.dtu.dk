from django.urls import path
from .views import hello_world


urlpatterns = [
    path('defender/v1.0/get-machine/', hello_world),
]
