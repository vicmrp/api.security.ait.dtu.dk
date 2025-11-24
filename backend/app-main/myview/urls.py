from django.urls import include, path, reverse_lazy
from django.contrib.auth import views as auth_views
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from .views import FrontpagePageView, SwaggerPageView # , MFAResetPageView, AjaxView
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.views.generic import RedirectView
from django.http import HttpResponseForbidden
from django.views.decorators.clickjacking import xframe_options_sameorigin

schema_view = get_schema_view(
   openapi.Info(
      title="API",
      default_version='v1',
      description="A simple API",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="vicre@dtu.dk"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)


@login_required
@xframe_options_sameorigin
def schema_swagger_ui_embedded(request, *args, **kwargs):
    return schema_view.with_ui('swagger', cache_timeout=0)(request, *args, **kwargs)


def my_view_fobidden_access(request):
   return HttpResponseForbidden('Only IT staff is permitted to access this site. Use your admin account to login.')


urlpatterns = [
   path('swagger/', SwaggerPageView.as_view(), name='schema-swagger-ui'),
   path('swagger/embed/', schema_swagger_ui_embedded, name='schema-swagger-ui-embedded'),
   path('only-allowed-for-it-staff/', my_view_fobidden_access),
]


try:
   from .views import FrontpagePageView

   urlpatterns += [
      path('', FrontpagePageView.as_view(), name='frontpage'),
      path('frontpage/', FrontpagePageView.as_view(), name='frontpage'),
   ]
except ImportError:
    print("FrontpagePageView model is not available for registration in the admin site.")
    pass


try:
   from .views import BugReportView

   urlpatterns += [
      path('bug-report/', BugReportView.as_view(), name='bug-report'),
   ]
except ImportError:
   print("BugReportView is not available for registration in the admin site.")
   pass


try:
   from .views import MFAResetPageView

   urlpatterns += [
      path('mfa-reset/', MFAResetPageView.as_view(), name='mfa-reset'),
      path('mfa-reset/user/<str:user_principal_id>/delete-authentication/<str:authentication_id>/', MFAResetPageView.as_view(), name='delete-auth-method'),
   ]

except ImportError:
    print("MFAResetPageView model is not available for registration in the admin site.")
    pass


try:  
   from .views import ActiveDirectoryCopilotView

   urlpatterns += [
      path('active-directory-copilot/', ActiveDirectoryCopilotView.as_view(), name='active-directory-copilot'),
   ]

except ImportError:
    print("MFAResetPageView model is not available for registration in the admin site.")
    pass



try:
   from .ajax_view import AjaxView
   from .views import api_token_view, rotate_api_token_view

   urlpatterns += [
      path('ajax/', AjaxView.as_view(), name='ajax'),
      path('api/token/', api_token_view, name='api-token'),
      path('api/token/rotate/', rotate_api_token_view, name='api-token-rotate'),
   ]

except ImportError:
   print("AjaxView model is not available for registration in the admin site.")
   pass
