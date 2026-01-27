# accounts/api/urls_api.py (updated)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.urls import reverse
from events.api.calendar_urls import urlpatterns as calendar_api_urls
from . import views
from . import views_professionals

# @api_view(['GET'])
# def api_root(request):
#     """
#     API Root - List all available endpoints
#     """
#     # Build absolute URIs manually to avoid reverse errors
#     base_url = request.build_absolute_uri('/')[:-1]  # Remove trailing slash
#
#     endpoints = {
#         'authentication': {
#             'register': f'{base_url}/api/v1/auth/register/',
#             'login': f'{base_url}/api/v1/auth/login/',
#             'logout': f'{base_url}/api/v1/auth/logout/',
#             'refresh': f'{base_url}/api/v1/auth/refresh/',
#         },
#         'dashboard': {
#             'home': f'{base_url}/api/v1/dashboard/home/',
#             'switch_profile': f'{base_url}/api/v1/dashboard/switch-profile/',
#             'profile_edit': f'{base_url}/api/v1/dashboard/profile/edit/',
#             'favorites': f'{base_url}/api/v1/dashboard/favorites/',
#             'favorite_toggle': f'{base_url}/api/v1/dashboard/favorites/toggle/',
#             'currency': f'{base_url}/api/v1/dashboard/currency/',
#             'languages': f'{base_url}/api/v1/dashboard/languages/',
#             'media_section': f'{base_url}/api/v1/dashboard/media/normal/'.replace('normal/', '{kind}/'),
#             'terms': f'{base_url}/api/v1/dashboard/terms/',
#             'support': f'{base_url}/api/v1/dashboard/support/',
#         },
#         'news': {
#             'list': f'{base_url}/api/v1/news/',
#             'detail': f'{base_url}/api/v1/news/slug/'.replace('slug/', '{slug}/'),
#         },
#         'admin': {
#             'crud_home': f'{base_url}/api/v1/admin/crud/',
#             'users': f'{base_url}/api/v1/admin/crud/users/',
#             'professions': f'{base_url}/api/v1/admin/crud/professions/',
#             'event_categories': f'{base_url}/api/v1/admin/crud/event-categories/',
#             'languages': f'{base_url}/api/v1/admin/crud/languages/',
#             'currencies': f'{base_url}/api/v1/admin/crud/currencies/',
#             'exchange_rates': f'{base_url}/api/v1/admin/crud/exchange-rates/',
#             'news_posts': f'{base_url}/api/v1/admin/crud/news/',
#         },
#         'user': {
#             'profile': f'{base_url}/api/v1/user/profile/',
#             'profile_avatar': f'{base_url}/api/v1/user/profile/avatar/',
#             'dashboard': f'{base_url}/api/v1/user/dashboard/',
#         },
#         'media': {
#             'upload': f'{base_url}/api/v1/upload/normal_photos/'.replace('normal_photos/', '{media_type}/'),
#         },
#         'search': {
#             'professionals': f'{base_url}/api/v1/search/professionals/',
#         },
#         'utility': {
#             'exchange_rates': f'{base_url}/api/v1/exchange-rates/',
#         },
#         'collections': {
#             'professions': f'{base_url}/api/v1/professions/',
#             'reviews': f'{base_url}/api/v1/reviews/',
#             'favorites': f'{base_url}/api/v1/favorites/',
#             'news': f'{base_url}/api/v1/news/',
#             'languages': f'{base_url}/api/v1/languages/',
#             'currencies': f'{base_url}/api/v1/currencies/',
#             'profiles': f'{base_url}/api/v1/profiles/',
#         },
#         # ============ NEW: Professionals Endpoints ============
#         'professionals': {
#             'list': f'{base_url}/api/v1/professionals/',
#             'detail': f'{base_url}/api/v1/professionals/1/'.replace('1/', '{id}/'),
#             'filter_options': f'{base_url}/api/v1/professionals/filter-options/',
#             'top': f'{base_url}/api/v1/professionals/top/',
#             'recommended': f'{base_url}/api/v1/professionals/recommended/',
#             'price_range': f'{base_url}/api/v1/professionals/price-range/',
#         },
#         'professions': {
#             'tree': f'{base_url}/api/v1/professions/tree/',
#             'list': f'{base_url}/api/v1/professions/',
#         },
#         # In your api_root function, add this section:
#         'events': {
#             'list': f'{base_url}/api/v1/events/',
#             'detail': f'{base_url}/api/v1/events/1/'.replace('1/', '{id}/'),
#             'create': f'{base_url}/api/v1/events/create/',
#             'my_events': f'{base_url}/api/v1/events/my-events/',
#             'categories': f'{base_url}/api/v1/events/categories/',
#             'categories_tree': f'{base_url}/api/v1/events/categories/tree/',
#             'offer_threads': f'{base_url}/api/v1/events/offer-threads/',
#             'busy_times': f'{base_url}/api/v1/events/busy-times/',
#             'filter_options': f'{base_url}/api/v1/events/filter-options/',
#             'stats': f'{base_url}/api/v1/events/stats/',
#         },
#         # In your api_root function, add this section:
#         'offers': {
#             'inbox': f'{base_url}/api/v1/events/offers/inbox/',
#             'inbox_stats': f'{base_url}/api/v1/events/offers/inbox/stats/',
#             'thread': f'{base_url}/api/v1/events/offers/threads/1/'.replace('1/', '{event_id}/'),
#             'send_offer': f'{base_url}/api/v1/events/offers/events/1/send-offer/'.replace('1/', '{event_id}/'),
#             'counter_offer': f'{base_url}/api/v1/events/offers/threads/1/counter-offer/'.replace('1/', '{thread_id}/'),
#             'send_chat': f'{base_url}/api/v1/events/offers/threads/1/chat/'.replace('1/', '{thread_id}/'),
#             'offer_action': f'{base_url}/api/v1/events/offers/events/1/professionals/2/action/'.replace('1/', '{event_id}/').replace('2/', '{pro_id}/'),
#             'booking_request': f'{base_url}/api/v1/events/offers/booking-request/',
#             'quick_booking': f'{base_url}/api/v1/events/offers/quick-booking/',
#             'thread_messages': f'{base_url}/api/v1/events/offers/threads/1/messages/'.replace('1/', '{thread_id}/'),
#             'currencies': f'{base_url}/api/v1/events/offers/currencies/',
#         },
#     }
#     return Response(endpoints)

# Create router
@api_view(['GET'])
def api_root(request):
    """
    API Root - List all available endpoints
    """
    base_url = request.build_absolute_uri('/')[:-1]

    endpoints = {
        'authentication': {
            'register': f'{base_url}/api/v1/auth/register/',
            'login': f'{base_url}/api/v1/auth/login/',
            'logout': f'{base_url}/api/v1/auth/logout/',
            'refresh': f'{base_url}/api/v1/auth/refresh/',
        },

        'dashboard': {
            'home': f'{base_url}/api/v1/dashboard/home/',
            'switch_profile': f'{base_url}/api/v1/dashboard/switch-profile/',
            'profile_edit': f'{base_url}/api/v1/dashboard/profile/edit/',
            'favorites': f'{base_url}/api/v1/dashboard/favorites/',
            'favorite_toggle': f'{base_url}/api/v1/dashboard/favorites/toggle/',
            'currency': f'{base_url}/api/v1/dashboard/currency/',
            'languages': f'{base_url}/api/v1/dashboard/languages/',
            'media_section': f'{base_url}/api/v1/dashboard/media/{{kind}}/',
            'upload': f'{base_url}/api/v1/upload/normal_photos/'.replace('normal_photos/', '{media_type}/'),
            'terms': f'{base_url}/api/v1/dashboard/terms/',
            'support': f'{base_url}/api/v1/dashboard/support/',
        },

        'news': {
            'list': f'{base_url}/api/v1/news/',
            'detail': f'{base_url}/api/v1/news/{{slug}}/',
            'unread_count': f'{base_url}/api/v1/news/unread-count/',
        },

        'professionals': {
            'list': f'{base_url}/api/v1/professionals/',
            'detail': f'{base_url}/api/v1/professionals/{{id}}/',
            'filter_options': f'{base_url}/api/v1/professionals/filter-options/',
            'top': f'{base_url}/api/v1/professionals/top/',
            'recommended': f'{base_url}/api/v1/professionals/recommended/',
            'price_range': f'{base_url}/api/v1/professionals/price-range/',
            'search': f'{base_url}/api/v1/search/professionals/',
        },

        'professions': {
            'tree': f'{base_url}/api/v1/professions/tree/',
            'list': f'{base_url}/api/v1/professions/',
        },

        # ================= EVENTS =================
        'events': {
            'list': f'{base_url}/api/v1/events/',
            'detail': f'{base_url}/api/v1/events/{{id}}/',
            'create': f'{base_url}/api/v1/events/',
            'my_events': f'{base_url}/api/v1/events/my-events/',
            'booked_events': f'{base_url}/api/v1/events/booked-events/',
            'upcoming': f'{base_url}/api/v1/events/upcoming/',
            'filter_options': f'{base_url}/api/v1/events/filter-options/',
            'stats': f'{base_url}/api/v1/events/stats/',
        },

        # ================= CALENDAR =================
        'calendar': {
            'month_view': f'{base_url}/api/v1/calendar/month/',
            'events_by_date': f'{base_url}/api/v1/calendar/events/',
        },

        # ================= BUSY TIMES =================
        'busy_times': {
            'list': f'{base_url}/api/v1/busy-times/',
            'create': f'{base_url}/api/v1/busy-times/',
            'delete_day': f'{base_url}/api/v1/busy-times/delete-day/',
            'date_range': f'{base_url}/api/v1/busy-times/date-range/',
        },

        # ================= OFFERS =================
        'offers': {
            'threads': f'{base_url}/api/v1/offer-threads/',
            'inbox_stats': f'{base_url}/api/v1/offer-threads/inbox/stats/',
            'thread_messages': f'{base_url}/api/v1/offer-threads/{{thread_id}}/messages/',
            'messages': f'{base_url}/api/v1/offer-messages/',
            'accept_offer': f'{base_url}/api/v1/offer-messages/{{id}}/accept/',
            'reject_offer': f'{base_url}/api/v1/offer-messages/{{id}}/reject/',
        },

        # ================= ADMIN =================
        'admin': {
            'crud_home': f'{base_url}/api/v1/admin/crud/',
            'users': f'{base_url}/api/v1/admin/crud/users/',
            'professions': f'{base_url}/api/v1/admin/crud/professions/',
            'event_categories': f'{base_url}/api/v1/admin/crud/event-categories/',
            'languages': f'{base_url}/api/v1/admin/crud/languages/',
            'currencies': f'{base_url}/api/v1/admin/crud/currencies/',
            'exchange_rates': f'{base_url}/api/v1/admin/crud/exchange-rates/',
            'news_posts': f'{base_url}/api/v1/admin/crud/news/',
        },
    }

    return Response(endpoints)
router = DefaultRouter()

# Register viewsets with explicit basenames
router.register('professions', views.ProfessionViewSet, basename='api-profession')
router.register('reviews', views.ReviewViewSet, basename='api-review')
router.register('favorites', views.FavoriteViewSet, basename='api-favorite')
router.register('news', views.NewsViewSet, basename='api-news')
router.register('languages', views.LanguageViewSet, basename='api-language')
router.register('currencies', views.CurrencyViewSet, basename='api-currency')
router.register('profiles', views.PublicProfileViewSet, basename='api-profile')

urlpatterns = [
    # API Root
    path('', api_root, name='api-root'),
    path('', include(calendar_api_urls)),

    # Authentication
    path('auth/register/', views.register_api, name='api-register'),
    path('auth/login/', views.login_api, name='api-login'),
    path('auth/logout/', views.logout_api, name='api-logout'),
    path('auth/refresh/', views.refresh_token_api, name='api-refresh'),

    # User Profile
    path('user/profile/', views.UserProfileViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'update'
    }), name='api-user-profile'),

    path('user/profile/avatar/', views.UserProfileViewSet.as_view({
        'post': 'upload_avatar'
    }), name='api-upload-avatar'),

    path('user/dashboard/', views.UserProfileViewSet.as_view({
        'get': 'dashboard'
    }), name='api-dashboard'),

    # Media Upload
    path('upload/<str:media_type>/', views.MediaUploadView.as_view(), name='api-media-upload'),

    # Search
    path('search/professionals/', views.ProfessionalSearchView.as_view(), name='api-search-professionals'),

    # Exchange Rates
    path('exchange-rates/', views.ExchangeRateView.as_view(), name='api-exchange-rates'),

    # Dashboard API
    path('', include('accounts.api.urls_dashboard_api')),

    # Include router URLs
    path('', include(router.urls)),

    # Professionals List
    path('professionals/', views_professionals.ProfessionalsListView.as_view(), name='api-professionals-list'),
    path('professionals/<int:pk>/', views_professionals.ProfessionalDetailView.as_view(),
         name='api-professional-detail'),
    path('professionals/filter-options/', views_professionals.FilterOptionsView.as_view(),
         name='api-professionals-filter-options'),
    path('professionals/top/', views_professionals.TopProfessionalsView.as_view(), name='api-professionals-top'),
    path('professionals/recommended/', views_professionals.RecommendedProfessionalsView.as_view(),
         name='api-professionals-recommended'),
    path('professionals/price-range/', views_professionals.PriceRangeView.as_view(),
         name='api-professionals-price-range'),
    path('professions/tree/', views_professionals.ProfessionTreeView.as_view(), name='api-professions-tree'),
]