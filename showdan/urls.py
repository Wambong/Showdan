from django.conf import settings
from .views import home_view
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
urlpatterns = [
    path("", home_view, name="home"),
    path("secrets-bunker/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path('account/', include('allauth.urls')),
    path("events/", include("events.urls")),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)