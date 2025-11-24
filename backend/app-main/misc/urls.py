from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import JsonValueExtractor, GenerateEmail

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('misc/my-mfa-extractor', JsonValueExtractor.as_view({'post': 'create'})),
    path('misc/my-mfa-email-body', GenerateEmail.as_view({'post': 'create'})),
]
