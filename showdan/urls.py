from django.conf import settings
from .views import home_view
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf.urls.i18n import i18n_patterns
urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
]

urlpatterns += i18n_patterns(
    path("", home_view, name="home"),
    path("secrets-bunker/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path('account/', include('allauth.urls')),
    path("events/", include("events.urls")),


    # API URLs
    path('api/v1/', include('accounts.api.urls_api')),

    # Events API (you'll need to create similar for events)
    path('api/v1/events/', include('events.api.urls')),

    # JWT Token endpoints
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
)


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)