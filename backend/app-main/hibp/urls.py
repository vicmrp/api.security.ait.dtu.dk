from django.urls import path

from . import views

urlpatterns = [
    path("hibp/v3/subscribeddomains", views.SubscriptionDomainsView.as_view()),
    path("hibp/v3/subscription/status", views.SubscriptionStatusView.as_view()),
    path("hibp/v3/breacheddomain/<str:domain>", views.BreachedDomainView.as_view()),
    path("hibp/v3/dataclasses", views.DataClassesView.as_view()),
    path("hibp/v3/breachedaccount/<str:account>", views.BreachedAccountView.as_view()),
    path("hibp/v3/breaches", views.AllBreachesView.as_view()),
    path("hibp/v3/breach/<str:name>", views.SingleBreachView.as_view()),
    path("hibp/v3/pasteaccount/<str:account>", views.PasteAccountView.as_view()),
    path(
        "hibp/v3/stealerlogsbyemaildomain/<str:domain>",
        views.StealerLogsByEmailDomainView.as_view(),
    ),
    path("hibp/v3/stealerlogsbyemail/<str:account>", views.StealerLogsByEmailView.as_view()),
    path(
        "hibp/v3/stealerlogsbywebsitedomain/<str:domain>",
        views.StealerLogsByWebsiteDomainView.as_view(),
    ),
    path("hibp/range/<str:prefix>", views.PwnedPasswordsRangeView.as_view()),
]
