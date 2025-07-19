"""
prudentia URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

# API URL patterns
api_urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    path('accounts/', include('apps.accounts.urls')),
    path('clients/', include('apps.clients.urls')),
    path('core/', include('apps.core.urls')), # If core app has specific API endpoints
    path('deadlines/', include('apps.deadlines.urls')),
    path('documents/', include('apps.documents.urls')),
    path('finance/', include('apps.finance.urls')),
    path('forms/', include('apps.forms_integration.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('pje/', include('apps.pje_monitoring.urls')),
    path('processes/', include('apps.processes.urls')),
    path('signatures/', include('apps.signatures.urls')),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(api_urlpatterns)),
    # Include DRF's login/logout views for the browsable API (optional, useful for development)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# It's good practice to define a health check endpoint
# from django.http import HttpResponse
# urlpatterns.append(path('health/', lambda request: HttpResponse("OK", status=200)))
