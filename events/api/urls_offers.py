# events/api/urls_offers.py
from django.urls import path
from . import views_offers

urlpatterns = [
    # ============ Offer Threads ============
    path('threads/<int:event_id>/', views_offers.OfferThreadView.as_view(), name='api-offer-thread'),

    # ============ Sending Offers ============
    path('events/<int:event_id>/send-offer/', views_offers.SendOfferView.as_view(), name='api-send-offer'),
    path('threads/<int:thread_id>/counter-offer/', views_offers.SendCounterOfferView.as_view(),
         name='api-counter-offer'),
    path('threads/<int:thread_id>/chat/', views_offers.SendChatMessageView.as_view(), name='api-send-chat'),

    # ============ Offer Actions ============
    path('events/<int:event_id>/professionals/<int:pro_id>/action/', views_offers.OfferActionView.as_view(),
         name='api-offer-action'),

    # ============ Inbox ============
    path('inbox/', views_offers.OffersInboxView.as_view(), name='api-offers-inbox'),
    path('inbox/stats/', views_offers.InboxStatsView.as_view(), name='api-inbox-stats'),

    # ============ Booking Requests ============
    path('booking-request/', views_offers.BookingRequestView.as_view(), name='api-booking-request'),
    path('quick-booking/', views_offers.QuickBookingView.as_view(), name='api-quick-booking'),

    # ============ Utility ============
    path('threads/<int:thread_id>/messages/', views_offers.OfferThreadMessagesView.as_view(),
         name='api-thread-messages'),
    path('threads/<int:thread_id>/mark-read/', views_offers.MarkMessagesReadView.as_view(), name='api-mark-read'),
    path('currencies/', views_offers.AvailableCurrenciesView.as_view(), name='api-offer-currencies'),
]