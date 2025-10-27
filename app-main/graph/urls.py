from django.urls import path

from .views import (
    DeleteMfaView,
    DeletePhoneView,
    DeleteSoftwareMfaView,
    GetUserView,
    IdentityLogonEventsView,
    ListUserAuthenticationMethodsView,
)

urlpatterns = [
    path('graph/v1.0/get-user/<str:user>', GetUserView.as_view()),
    path(
        'graph/v1.0/identitylogonevents/<str:user>',
        IdentityLogonEventsView.as_view(),
    ),
    path(
        'graph/v1.0/list/<str:user_id__or__user_principalname>/authentication-methods',
        ListUserAuthenticationMethodsView.as_view(),
    ),
    path(
        'graph/v1.0/users/<str:user_id__or__user_principalname>/microsoft-authentication-methods/<str:microsoft_authenticator_method_id>',
        DeleteMfaView.as_view(),
    ),
    path(
        'graph/v1.0/users/<str:user_id__or__user_principalname>/phone-authentication-methods/<str:phone_authenticator_method_id>',
        DeletePhoneView.as_view(),
    ),
    path(
        'graph/v1.0/users/<str:user_id__or__user_principalname>/software-authentication-methods/<str:software_oath_method_id>',
        DeleteSoftwareMfaView.as_view(),
    ),
]
