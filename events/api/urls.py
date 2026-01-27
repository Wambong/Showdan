# events/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import views_offers
# Create router for any ViewSets (if needed)
router = DefaultRouter()

urlpatterns = [
    # ============ calendar ============

    # ============ Events ============
    path('', views.EventListView.as_view(), name='api-events-list'),
    path('<int:id>/', views.EventDetailView.as_view(), name='api-event-detail'),
    path('create/', views.EventCreateView.as_view(), name='api-event-create'),
    path('<int:id>/update/', views.EventUpdateView.as_view(), name='api-event-update'),
    path('<int:id>/delete/', views.EventDeleteView.as_view(), name='api-event-delete'),
    path('my-events/', views.UserEventsView.as_view(), name='api-user-events'),

    # ============ Event Categories ============
    path('categories/', views.EventCategoryListView.as_view(), name='api-event-categories'),
    path('categories/tree/', views.EventCategoryTreeView.as_view(), name='api-event-categories-tree'),
    path('categories/create/', views.EventCategoryCreateView.as_view(), name='api-event-category-create'),

    # ============ Offer Threads ============
    path('offer-threads/', views.OfferThreadListView.as_view(), name='api-offer-threads'),
    path('offer-threads/<int:id>/', views.OfferThreadDetailView.as_view(), name='api-offer-thread-detail'),
    path('offer-threads/create/', views.OfferThreadCreateView.as_view(), name='api-offer-thread-create'),

    # ============ Offer Messages ============
    path('offer-threads/<int:thread_id>/messages/', views.OfferMessageListView.as_view(), name='api-offer-messages'),
    path('offer-threads/<int:thread_id>/messages/create/', views.OfferMessageCreateView.as_view(),
         name='api-offer-message-create'),
    path('offer-messages/<int:id>/update-status/', views.OfferMessageUpdateStatusView.as_view(),
         name='api-offer-message-update-status'),

    # ============ Busy Times ============
    path('busy-times/', views.BusyTimeListView.as_view(), name='api-busy-times'),
    path('busy-times/create/', views.BusyTimeCreateView.as_view(), name='api-busy-time-create'),
    path('busy-times/<int:id>/', views.BusyTimeDetailView.as_view(), name='api-busy-time-detail'),

    # ============ Utility ============
    path('filter-options/', views.EventFilterOptionsView.as_view(), name='api-events-filter-options'),
    path('stats/', views.EventStatsView.as_view(), name='api-events-stats'),

    # Include offers URLs
    path('offers/', include('events.api.urls_offers')),

    # Include router URLs
    path('', include(router.urls)),
]