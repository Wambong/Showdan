# accounts/api/urls_dashboard_api.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views_dashboard_api

# Create router for CRUD viewsets
router = DefaultRouter()
router.register(r'admin/crud/professions', views_dashboard_api.ProfessionCRUDViewSet, basename='admin-profession')
router.register(r'admin/crud/event-categories', views_dashboard_api.EventCategoryCRUDViewSet,
                basename='admin-eventcategory')
router.register(r'admin/crud/languages', views_dashboard_api.LanguageCRUDViewSet, basename='admin-language')
router.register(r'admin/crud/currencies', views_dashboard_api.CurrencyCRUDViewSet, basename='admin-currency')
router.register(r'admin/crud/exchange-rates', views_dashboard_api.ExchangeRateCRUDViewSet,
                basename='admin-exchangerate')
router.register(r'admin/crud/news', views_dashboard_api.NewsPostCRUDViewSet, basename='admin-news')

urlpatterns = [
    # Dashboard Home
    path('dashboard/home/', views_dashboard_api.DashboardHomeView.as_view(), name='api-dashboard-home'),

    # Switch Profile
    path('dashboard/switch-profile/', views_dashboard_api.SwitchProfileView.as_view(), name='api-switch-profile'),

    # Profile Edit
    path('dashboard/profile/edit/', views_dashboard_api.ProfileEditView.as_view(), name='api-profile-edit'),

    # Favorites
    path('dashboard/favorites/', views_dashboard_api.FavoritesView.as_view(), name='api-favorites'),
    path('dashboard/favorites/toggle/', views_dashboard_api.FavoriteToggleView.as_view(), name='api-favorite-toggle'),

    # Currency
    path('dashboard/currency/', views_dashboard_api.CurrencyView.as_view(), name='api-currency'),

    # Languages
    path('dashboard/languages/', views_dashboard_api.LanguageView.as_view(), name='api-languages'),

    # Media Sections
    path('dashboard/media/<str:kind>/', views_dashboard_api.MediaSectionView.as_view(), name='api-media-section'),

    # Terms & Support
    path('dashboard/terms/', views_dashboard_api.TermsView.as_view(), name='api-terms'),
    path('dashboard/support/', views_dashboard_api.SupportView.as_view(), name='api-support'),

    # News (public/authenticated)
    path('news/', views_dashboard_api.NewsListView.as_view(), name='api-news-list'),
    path('news/<str:slug>/', views_dashboard_api.NewsDetailView.as_view(), name='api-news-detail'),

    # Admin CRUD Home
    path('admin/crud/', views_dashboard_api.CRUDHomeView.as_view(), name='api-admin-crud-home'),

    # Admin User Management
    path('admin/crud/users/', views_dashboard_api.UserCRUDView.as_view(), name='api-admin-users'),
    path('admin/crud/users/<int:pk>/', views_dashboard_api.UserCRUDDetailView.as_view(), name='api-admin-user-detail'),
    path('admin/crud/users/<int:pk>/toggle-active/', views_dashboard_api.UserToggleActiveView.as_view(),
         name='api-admin-user-toggle-active'),
    path('admin/crud/users/<int:pk>/toggle-staff/', views_dashboard_api.UserToggleStaffView.as_view(),
         name='api-admin-user-toggle-staff'),

    # Include router URLs
    path('', include(router.urls)),
]