from django.contrib import admin
from rest_framework.authtoken.views import ObtainAuthToken
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import run_migrate
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    
    # Serve frontend
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('upload/', TemplateView.as_view(template_name='upload.html')),
    path('files/', TemplateView.as_view(template_name='files.html')),
    path('analytics/', TemplateView.as_view(template_name='analytics.html')),
    path('api/auth/token/', ObtainAuthToken.as_view(), name='get_token'),
    path("api/system/migrate/", run_migrate),
    path('billing/', TemplateView.as_view(template_name='billing.html')),
    path('branding/', TemplateView.as_view(template_name='branding.html')),
    path('security/', TemplateView.as_view(template_name='security.html')),
    path('bot/', TemplateView.as_view(template_name='bot.html')),
    path('verification/', TemplateView.as_view(template_name='verification.html')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)