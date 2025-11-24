from django.urls import path
from .views import APIDocumentationView, APIEndpointsListView

urlpatterns = [
    path('openapi/v1.0/documentation/<str:endpoint_name>/', APIDocumentationView.as_view(), name='api-documentation'),
    path('openapi/v1.0/endpoints/', APIEndpointsListView.as_view(), name='api-endpoints-list'),
]