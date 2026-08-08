from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('resumes.urls')),
    path('jobs/', include('jobs.urls')),
    path('career/', include('career.urls')),
    
    # REST API endpoints
    path('api/accounts/', include('accounts.api_urls')),
    path('api/', include('resumes.api_urls')),
    path('api/', include('jobs.api_urls')),
    path('api/', include('career.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
