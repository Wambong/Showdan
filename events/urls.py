from django.urls import path
from . import views
from .views_offers import (
    offer_thread_view,
    send_offer_message,
    counter_offer_view,
    accept_offer_view,
    reject_offer_view,
    offers_inbox_view,
    send_chat_message_view,
    booking_request_from_calendar_view
)

from .views_calendar import (
    calendar_view,
    busytime_delete_day
)
app_name = "events"

urlpatterns = [
    path("categories/create/", views.category_create_view, name="category_create"),
    path("create/", views.event_create_view, name="event_create"),
    path("", views.events_list_view, name="list"),
    path("<int:event_id>/", views.event_detail_view, name="detail"),

]




urlpatterns += [
    path("<int:event_id>/offers/", offer_thread_view, name="offer_thread"),
    path("<int:event_id>/offers/send/", send_offer_message, name="offer_send"),

    # creator actions (creator selects pro thread)
    path("<int:event_id>/offers/<int:pro_id>/counter/", counter_offer_view, name="offer_counter"),
    path("<int:event_id>/offers/<int:pro_id>/accept/", accept_offer_view, name="offer_accept"),
    path("<int:event_id>/offers/<int:pro_id>/reject/", reject_offer_view, name="offer_reject"),

    path("my-offers/", offers_inbox_view, name="offers_inbox"),
    path("offers/thread/<int:thread_id>/send/", send_chat_message_view, name="offer_chat_send"),

    path("calendar/", calendar_view, name="calendar"),
    path("calendar/busy/delete/", busytime_delete_day, name="busy_delete_day"),
    path("booking-request/<int:pro_id>/", booking_request_from_calendar_view, name="booking_request_calendar"),

]
