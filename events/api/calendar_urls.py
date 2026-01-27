# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from .views_calendar import (
#     EventViewSet, EventCategoryViewSet, BusyTimeViewSet,
#     OfferThreadViewSet, OfferMessageViewSet,
#     calendar_month_view, calendar_events_by_date
# )
#
#
# urlpatterns = [
#
#     # Calendar endpoints
#     path('calendar/month/', calendar_month_view, name='calendar-month'),
#     path('calendar/events/', calendar_events_by_date, name='calendar-events'),
#
#     # Additional endpoints
#     path('events/my-events/', EventViewSet.as_view({'get': 'my_events'}), name='my-events'),
#     path('events/booked-events/', EventViewSet.as_view({'get': 'booked_events'}), name='booked-events'),
#     path('events/upcoming/', EventViewSet.as_view({'get': 'upcoming'}), name='upcoming-events'),
#     path('events/filter-options/', EventViewSet.as_view({'get': 'filter_options'}), name='event-filter-options'),
#     path('events/stats/', EventViewSet.as_view({'get': 'stats'}), name='event-stats'),
#
#     # Busy times additional endpoints
#     path('busy-times/delete-day/', BusyTimeViewSet.as_view({'post': 'delete_day'}), name='busytime-delete-day'),
#     path('busy-times/date-range/', BusyTimeViewSet.as_view({'get': 'date_range'}), name='busytime-date-range'),
#
#     # Offer threads additional endpoints
#     path('offer-threads/inbox/stats/', OfferThreadViewSet.as_view({'get': 'inbox_stats'}), name='inbox-stats'),
#     path('offer-threads/<int:pk>/messages/', OfferThreadViewSet.as_view({'get': 'messages'}), name='thread-messages'),
#
#     # Offer messages additional endpoints
#     path('offer-messages/<int:pk>/accept/', OfferMessageViewSet.as_view({'post': 'accept'}), name='accept-offer'),
#     path('offer-messages/<int:pk>/reject/', OfferMessageViewSet.as_view({'post': 'reject'}), name='reject-offer'),
# ]

# calendar_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_calendar import (
    EventViewSet, EventCategoryViewSet, BusyTimeViewSet,
    OfferThreadViewSet, OfferMessageViewSet,
    calendar_month_view, calendar_events_by_date
)

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'event-categories', EventCategoryViewSet, basename='eventcategory')
router.register(r'busy-times', BusyTimeViewSet, basename='busytime')
router.register(r'offer-threads', OfferThreadViewSet, basename='offerthread')
router.register(r'offer-messages', OfferMessageViewSet, basename='offermessage')

urlpatterns = [
    path('', include(router.urls)),

    # Calendar endpoints
    path('calendar/month/', calendar_month_view, name='calendar-month'),
    path('calendar/events/', calendar_events_by_date, name='calendar-events'),

    # Additional endpoints
    path('events/my-events/', EventViewSet.as_view({'get': 'my_events'}), name='my-events'),
    path('events/booked-events/', EventViewSet.as_view({'get': 'booked_events'}), name='booked-events'),
    path('events/upcoming/', EventViewSet.as_view({'get': 'upcoming'}), name='upcoming-events'),
    path('events/filter-options/', EventViewSet.as_view({'get': 'filter_options'}), name='event-filter-options'),
    path('events/stats/', EventViewSet.as_view({'get': 'stats'}), name='event-stats'),

    # Busy times additional endpoints
    path('busy-times/delete-day/', BusyTimeViewSet.as_view({'post': 'delete_day'}), name='busytime-delete-day'),
    path('busy-times/date-range/', BusyTimeViewSet.as_view({'get': 'date_range'}), name='busytime-date-range'),

    # Offer threads additional endpoints
    path('offer-threads/inbox/stats/', OfferThreadViewSet.as_view({'get': 'inbox_stats'}), name='inbox-stats'),
    path('offer-threads/<int:pk>/messages/', OfferThreadViewSet.as_view({'get': 'messages'}), name='thread-messages'),

    # Offer messages additional endpoints
    path('offer-messages/<int:pk>/accept/', OfferMessageViewSet.as_view({'post': 'accept'}), name='accept-offer'),
    path('offer-messages/<int:pk>/reject/', OfferMessageViewSet.as_view({'post': 'reject'}), name='reject-offer'),
]