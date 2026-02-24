from django.urls import path

from .views import HubCertShareEventsView

urlpatterns = [
    path('hub.cert.dk/shares/v2/<str:share_id>', HubCertShareEventsView.as_view()),
]
