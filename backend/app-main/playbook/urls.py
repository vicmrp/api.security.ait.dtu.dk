from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MyMFARejectedByUser

# router = DefaultRouter()

urlpatterns = [
    # path('', include(router.urls)),
    # path('api/playbook/my-mfa-extractor/', JsonValueExtractor.as_view({'post': 'create'})),
    # path('api/playbook/my-mfa-email-body/', GenerateEmail.as_view({'post': 'create'})),    
    # path('api/playbook/my-mfa-rejected-by-user/render-html', MyMFARejectedByUser.as_view({'post': 'render_html'})),
    # path('api/playbook/my-mfa-rejected-by-user/get-email', MyMFARejectedByUser.as_view({'post': 'get_email'})),
]
