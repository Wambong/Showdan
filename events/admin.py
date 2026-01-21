from django.contrib import admin
from .models import Event, EventCategory


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    list_filter = ("parent",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "start_datetime", "end_datetime", "location", "event_type", "created_by")
    list_filter = ("event_type", "start_datetime")
    search_fields = ("name", "location", "created_by__email", "created_by__first_name", "created_by__last_name")
    autocomplete_fields = ("created_by",)
    filter_horizontal = ("required_professions",)
