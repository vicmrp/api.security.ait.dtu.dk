from django.urls import path

from .views import ActiveDirectoryQueryAssistantView, ActiveDirectoryQueryView

urlpatterns = [
    path('active-directory/v1.0/query', ActiveDirectoryQueryView.as_view()),
    path('active-directory/v1.0/query-assistant', ActiveDirectoryQueryAssistantView.as_view()),
]

