from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SCCMViewSet_1_0_1

# router = DefaultRouter()

urlpatterns = [
    # path('', include(router.urls)),
    path('sccm/computer/v1-0-1/<str:computer_name>/', SCCMViewSet_1_0_1.as_view({'get': 'get_computerinfo'})),
]

