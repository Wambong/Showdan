from django.urls import path
from .views import (
    register_view,
    profile_view,
    profession_create_view,
    AccountLoginView,
    AccountLogoutView,
    profession_tree_view,
    profile_edit_view,
    public_profile_detail_view,
    profile_media_hub_view,
    create_review_view,
    dashboard_view
)
from . import views_dashboard as dv

app_name = "accounts"

urlpatterns = [
    path("register/", register_view, name="register"),

    path("login/", AccountLoginView.as_view(), name="login"),
    path("logout/", AccountLogoutView.as_view(), name="logout"),
    path("profile/", profile_view, name="profile"),
    path("professions/new/", profession_create_view, name="profession_create"),
    path("professions/tree/", profession_tree_view, name="profession_tree"),
    path("profile/edit/", profile_edit_view, name="profile_edit"),

    path("profiles/<int:pk>/", public_profile_detail_view, name="profile_detail"),
    path("profiles/<int:pk>/media/", profile_media_hub_view, name="profile_media"),
    path("profiles/<int:pk>/review/", create_review_view, name="create_review"),

    # dashboard partials (loaded into dash-main-card)
    path("dashboard/", dashboard_view, name="dashboard"),
    path("dashboard/home/", dv.dash_home, name="dash_home"),
    path("dashboard/switch-profile/", dv.dash_switch_profile, name="switch_profile"),
    path("dashboard/profile-edit/", dv.dash_profile_edit, name="dash_profile_edit"),
    path("dashboard/favorites/", dv.dash_favorites, name="favorites"),
    path("dashboard/language/", dv.dash_language, name="dash_language"),
    path("dashboard/currency/", dv.dash_currency, name="dash_currency"),
    path("dashboard/terms/", dv.dash_terms, name="terms"),
    path("dashboard/support/", dv.dash_support, name="support"),

    path("dashboard/crud/", dv.dash_crud_home, name="dash_crud_home"),

    path("dashboard/crud/professions/", dv.dash_crud_profession_list, name="dash_crud_profession_list"),
    path("dashboard/crud/professions/new/", dv.dash_crud_profession_create, name="dash_crud_profession_create"),
    path("dashboard/crud/professions/<int:pk>/edit/", dv.dash_crud_profession_edit,
         name="dash_crud_profession_edit"),
    path("dashboard/crud/professions/<int:pk>/delete/", dv.dash_crud_profession_delete,
         name="dash_crud_profession_delete"),

    path("dashboard/crud/event-categories/", dv.dash_crud_eventcategory_list, name="dash_crud_eventcategory_list"),
    path("dashboard/crud/event-categories/new/", dv.dash_crud_eventcategory_create,
         name="dash_crud_eventcategory_create"),
    path("dashboard/crud/event-categories/<int:pk>/edit/", dv.dash_crud_eventcategory_edit,
         name="dash_crud_eventcategory_edit"),
    path("dashboard/crud/event-categories/<int:pk>/delete/", dv.dash_crud_eventcategory_delete,
         name="dash_crud_eventcategory_delete"),

    path("dashboard/crud/languages/", dv.dash_crud_language_list, name="dash_crud_language_list"),
    path("dashboard/crud/languages/new/", dv.dash_crud_language_create, name="dash_crud_language_create"),
    path("dashboard/crud/languages/<int:pk>/edit/", dv.dash_crud_language_edit, name="dash_crud_language_edit"),
    path("dashboard/crud/languages/<int:pk>/delete/", dv.dash_crud_language_delete,
         name="dash_crud_language_delete"),


    path("dashboard/crud/currencies/", dv.dash_crud_currency_list, name="dash_crud_currency_list"),
    path("dashboard/crud/currencies/new/", dv.dash_crud_currency_create, name="dash_crud_currency_create"),
    path("dashboard/crud/currencies/<int:pk>/edit/", dv.dash_crud_currency_edit, name="dash_crud_currency_edit"),
    path("dashboard/crud/currencies/<int:pk>/delete/", dv.dash_crud_currency_delete,
         name="dash_crud_currency_delete"),

    path("dashboard/crud/exchange-rates/", dv.dash_crud_exchangerate_list, name="dash_crud_exchangerate_list"),
    path("dashboard/crud/exchange-rates/new/", dv.dash_crud_exchangerate_create,
         name="dash_crud_exchangerate_create"),
    path("dashboard/crud/exchange-rates/<int:pk>/edit/", dv.dash_crud_exchangerate_edit,
         name="dash_crud_exchangerate_edit"),
    path("dashboard/crud/exchange-rates/<int:pk>/delete/", dv.dash_crud_exchangerate_delete,
         name="dash_crud_exchangerate_delete"),

    path("dashboard/crud/users/", dv.dash_crud_users_list, name="dash_crud_users_list"),
    path("dashboard/crud/users/<int:pk>/edit/", dv.dash_crud_users_edit, name="dash_crud_users_edit"),
    path("dashboard/crud/users/<int:pk>/toggle-active/", dv.dash_crud_users_toggle_active,
         name="dash_crud_users_toggle_active"),
    path("dashboard/crud/users/<int:pk>/toggle-staff/", dv.dash_crud_users_toggle_staff,
         name="dash_crud_users_toggle_staff"),

]
