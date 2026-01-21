from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Accounts, Profession, Language, ProfessionalPhoto, Currency
@admin.register(Profession)
class ProfessionAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    list_filter = ("parent",)


@admin.register(Accounts)
class AccountsAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "account_type", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("account_type", "is_staff", "is_active")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "phone", "country", "city", "address", "date_of_birth", "profile_picture","professional_picture")}),
        ("Account", {"fields": ("account_type", "professions")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Pricing", {"fields": ("currency", "cost_per_hour", "cost_per_5_hours")}),

    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "first_name",
                "last_name",
                "password1",
                "password2",
                "account_type",
                "is_staff",
                "is_active",
            ),
        }),
    )

    filter_horizontal = ("groups", "user_permissions", "professions", "communication_languages", "event_languages")




@admin.register(ProfessionalPhoto)
class ProfessionalPhotoAdmin(admin.ModelAdmin):
    list_display = ("user", "uploaded_at")
    search_fields = ("user__email",)

from .models import AudioAcapellaCover, VideoAcapellaCover

@admin.register(AudioAcapellaCover)
class AudioAcapellaCoverAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "uploaded_at")
    search_fields = ("user__email", "title")

@admin.register(VideoAcapellaCover)
class VideoAcapellaCoverAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "uploaded_at")
    search_fields = ("user__email", "title")




@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("name", "sign")
    search_fields = ("name", "sign")