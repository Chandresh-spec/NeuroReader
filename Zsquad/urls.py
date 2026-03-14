from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from .views import index, serve_html

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', index),
    path('<slug:page>.html', serve_html),

    # Authentication endpoints
    path("api/auth/", include("accounts.urls")),

    # Library — file upload, list, serve, reading data
    path("api/library/", include("library.urls")),

    # AI features — simplify, structure, explain word
    path("api/ai/", include("ai_features.urls")),

    # Translation
    path("api/translator/", include("translator.urls")),

    # User Preferences
    path("api/preferences/", include("user_preferences.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
