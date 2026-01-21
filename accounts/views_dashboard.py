
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import (
    AccountsProfileForm,
    NormalPhotosUploadForm,
    ProfessionalPhotosUploadForm,
    AudioCoversUploadForm,
    VideoCoversUploadForm,
    DashCurrencyForm,
    DashLanguageForm,
)
from .models import AccountPhoto, ProfessionalPhoto, AudioAcapellaCover, VideoAcapellaCover
from django.contrib.admin.views.decorators import staff_member_required

User = get_user_model()

from .crud_forms import (
    ProfessionForm,
    EventCategoryForm,
    LanguageForm,
    CurrencyForm,
    ExchangeRateForm,
    AdminUserUpdateForm,
)
from .models import Profession, Language, Currency, ExchangeRate
from events.models import EventCategory


def _dash_render(request, template_name, ctx=None):
    """
    If HTMX request -> return partial content only.
    Else -> render full dashboard shell and let HTMX load the content.
    """
    ctx = ctx or {}
    if request.headers.get("HX-Request") == "true":
        return render(request, template_name, ctx)
    # fallback if user opens the URL directly (non-HTMX)
    return render(request, "accounts/dashboard.html", ctx)


@login_required
def dash_home(request):
    u = request.user
    is_pro = getattr(u, "account_type", None) == "professional"

    normal_photos = AccountPhoto.objects.filter(user=u).order_by("-id")
    professional_photos = ProfessionalPhoto.objects.filter(user=u).order_by("-id")
    audio_covers = AudioAcapellaCover.objects.filter(user=u).order_by("-id")
    video_covers = VideoAcapellaCover.objects.filter(user=u).order_by("-id")

    return _dash_render(
        request,
        "accounts/dash_pages/home.html",
        {
            "u": u,
            "is_pro": is_pro,
            "normal_photos": normal_photos,
            "professional_photos": professional_photos,
            "audio_covers": audio_covers,
            "video_covers": video_covers,
        },
    )

@login_required
def dash_switch_profile(request):
    u = request.user
    return _dash_render(request, "accounts/dash_pages/switch_profile.html", {"u": u,})


@login_required
def dash_profile_edit(request):
    u = request.user

    if request.method == "POST":
        form = AccountsProfileForm(request.POST, request.FILES, instance=u)

        photos_form = NormalPhotosUploadForm(request.POST, request.FILES)
        professional_form = ProfessionalPhotosUploadForm(request.POST, request.FILES)
        audio_form = AudioCoversUploadForm(request.POST, request.FILES)
        video_form = VideoCoversUploadForm(request.POST, request.FILES)

        if (
            form.is_valid()
            and photos_form.is_valid()
            and professional_form.is_valid()
            and audio_form.is_valid()
            and video_form.is_valid()
        ):
            form.save()

            # Normal photos
            for f in photos_form.cleaned_data.get("normal_images", []):
                AccountPhoto.objects.create(user=u, image=f)

            # Professional photos
            for f in professional_form.cleaned_data.get("professional_images", []):
                ProfessionalPhoto.objects.create(user=u, image=f)

            # Audio covers
            for f in audio_form.cleaned_data.get("audio_files", []):
                AudioAcapellaCover.objects.create(user=u, audio_file=f)

            # Video covers
            for f in video_form.cleaned_data.get("video_files", []):
                VideoAcapellaCover.objects.create(user=u, video_file=f)

            messages.success(request, "Profile updated successfully.")

            # ✅ If HTMX: tell browser to go back to dashboard home (or any url you want)
            if request.headers.get("HX-Request") == "true":
                resp = redirect("accounts:dashboard")  # change to your dashboard url name
                resp["HX-Redirect"] = resp.url
                return resp

            # Non-HTMX fallback
            return redirect("accounts:dashboard")

        messages.error(request, "Please correct the errors below.")

    else:
        form = AccountsProfileForm(instance=u)
        photos_form = NormalPhotosUploadForm()
        professional_form = ProfessionalPhotosUploadForm()
        audio_form = AudioCoversUploadForm()
        video_form = VideoCoversUploadForm()

    return _dash_render(
        request,
        "accounts/dash_pages/profile_edit.html",
        {
            "u": u,
            "form": form,
            "photos_form": photos_form,
            "professional_form": professional_form,
            "audio_form": audio_form,
            "video_form": video_form,
            "is_pro": getattr(u, "account_type", None) == "professional",
        },
    )

@login_required
def dash_favorites(request):
    u = request.user
    return _dash_render(request, "accounts/dash_pages/favorites.html", {"u": u,})


@login_required
def dash_currency(request):
    u = request.user

    if request.method == "POST":
        form = DashCurrencyForm(request.POST, instance=u)
        if form.is_valid():
            u.currency = form.cleaned_data["currency"]
            u.save(update_fields=["currency"])
            messages.success(request, "Currency updated.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DashCurrencyForm(instance=u)

    currencies = Currency.objects.all().order_by("name")
    return _dash_render(
        request,
        "accounts/dash_pages/currency.html",
        {"u": u, "form": form, "currencies": currencies},
    )


@login_required
def dash_language(request):
    u = request.user

    if request.method == "POST":
        form = DashLanguageForm(request.POST, instance=u)
        if form.is_valid():
            u.communication_languages.set(form.cleaned_data["communication_languages"])
            u.event_languages.set(form.cleaned_data["event_languages"])
            messages.success(request, "Languages updated.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DashLanguageForm(instance=u)

    languages = Language.objects.all().order_by("name")
    return _dash_render(
        request,
        "accounts/dash_pages/language.html",
        {"u": u, "form": form, "languages": languages},
    )

@login_required
def dash_terms(request):
    u = request.user
    return _dash_render(request, "accounts/dash_pages/terms.html", {"u": u,})


@login_required
def dash_support(request):
    u = request.user
    return _dash_render(request, "accounts/dash_pages/support.html", {"u": u,})



# --- CRUD NAV HOME ---
@staff_member_required
def dash_crud_home(request):
    return _dash_render(request, "accounts/dash_pages/crud/index.html", {})


# -------------------------
# Profession CRUD
# -------------------------
@staff_member_required
def dash_crud_profession_list(request):
    # qs = Profession.objects.select_related("parent").all().order_by("name")
    qs = Profession.objects.all().order_by("path")
    return _dash_render(request, "accounts/dash_pages/crud/profession_list.html", {"items": qs})

@staff_member_required
def dash_crud_profession_create(request):
    form = ProfessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profession created.")
        return redirect("accounts:dash_crud_profession_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New profession"})

@staff_member_required
def dash_crud_profession_edit(request, pk):
    obj = get_object_or_404(Profession, pk=pk)
    form = ProfessionForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profession updated.")
        return redirect("accounts:dash_crud_profession_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit profession"})

@staff_member_required
def dash_crud_profession_delete(request, pk):
    obj = get_object_or_404(Profession, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Profession deleted.")
        return redirect("accounts:dash_crud_profession_list")
    return _dash_render(request, "accounts/dash_pages/crud/confirm_delete.html", {"obj": obj, "title": "Delete profession"})


# -------------------------
# EventCategory CRUD
# -------------------------
@staff_member_required
def dash_crud_eventcategory_list(request):
    # qs = EventCategory.objects.select_related("parent").all().order_by("name")
    qs = EventCategory.objects.all().order_by("path")
    return _dash_render(request, "accounts/dash_pages/crud/eventcategory_list.html", {"items": qs})

@staff_member_required
def dash_crud_eventcategory_create(request):
    form = EventCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Event category created.")
        return redirect("accounts:dash_crud_eventcategory_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New event category"})

@staff_member_required
def dash_crud_eventcategory_edit(request, pk):
    obj = get_object_or_404(EventCategory, pk=pk)
    form = EventCategoryForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Event category updated.")
        return redirect("accounts:dash_crud_eventcategory_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit event category"})

@staff_member_required
def dash_crud_eventcategory_delete(request, pk):
    obj = get_object_or_404(EventCategory, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Event category deleted.")
        return redirect("accounts:dash_crud_eventcategory_list")
    return _dash_render(request, "accounts/dash_pages/crud/confirm_delete.html", {"obj": obj, "title": "Delete event category"})


# -------------------------
# Language CRUD
# -------------------------
@staff_member_required
def dash_crud_language_list(request):
    qs = Language.objects.all().order_by("name")
    return _dash_render(request, "accounts/dash_pages/crud/language_list.html", {"items": qs})

@staff_member_required
def dash_crud_language_create(request):
    form = LanguageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Language created.")
        return redirect("accounts:dash_crud_language_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New language"})

@staff_member_required
def dash_crud_language_edit(request, pk):
    obj = get_object_or_404(Language, pk=pk)
    form = LanguageForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Language updated.")
        return redirect("accounts:dash_crud_language_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit language"})

@staff_member_required
def dash_crud_language_delete(request, pk):
    obj = get_object_or_404(Language, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Language deleted.")
        return redirect("accounts:dash_crud_language_list")
    return _dash_render(request, "accounts/dash_pages/crud/confirm_delete.html", {"obj": obj, "title": "Delete language"})


# -------------------------
# Currency CRUD
# -------------------------
@staff_member_required
def dash_crud_currency_list(request):
    qs = Currency.objects.all().order_by("name")
    return _dash_render(request, "accounts/dash_pages/crud/currency_list.html", {"items": qs})

@staff_member_required
def dash_crud_currency_create(request):
    form = CurrencyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Currency created.")
        return redirect("accounts:dash_crud_currency_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New currency"})

@staff_member_required
def dash_crud_currency_edit(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    form = CurrencyForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Currency updated.")
        return redirect("accounts:dash_crud_currency_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit currency"})

@staff_member_required
def dash_crud_currency_delete(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Currency deleted.")
        return redirect("accounts:dash_crud_currency_list")
    return _dash_render(request, "accounts/dash_pages/crud/confirm_delete.html", {"obj": obj, "title": "Delete currency"})


# -------------------------
# ExchangeRate CRUD
# -------------------------
@staff_member_required
def dash_crud_exchangerate_list(request):
    qs = (
        ExchangeRate.objects
        .select_related("from_currency", "to_currency")
        .all()
        .order_by("-updated_at")
    )
    return _dash_render(request, "accounts/dash_pages/crud/exchangerate_list.html", {"items": qs})

@staff_member_required
def dash_crud_exchangerate_create(request):
    form = ExchangeRateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exchange rate created.")
        return redirect("accounts:dash_crud_exchangerate_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New exchange rate"})

@staff_member_required
def dash_crud_exchangerate_edit(request, pk):
    obj = get_object_or_404(ExchangeRate, pk=pk)
    form = ExchangeRateForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exchange rate updated.")
        return redirect("accounts:dash_crud_exchangerate_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit exchange rate"})

@staff_member_required
def dash_crud_exchangerate_delete(request, pk):
    obj = get_object_or_404(ExchangeRate, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Exchange rate deleted.")
        return redirect("accounts:dash_crud_exchangerate_list")
    return _dash_render(request, "accounts/dash_pages/crud/confirm_delete.html", {"obj": obj, "title": "Delete exchange rate"})



def staff_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_staff)(view_func))


@staff_required
def dash_crud_users_list(request):
    qs = User.objects.all().order_by("-date_joined")

    q = (request.GET.get("q") or "").strip()
    account_type = (request.GET.get("type") or "").strip()   # "personal" / "professional"
    staff = (request.GET.get("staff") or "").strip()         # "1" / "0"
    active = (request.GET.get("active") or "").strip()       # "1" / "0"

    if q:
        qs = qs.filter(
            Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(nickname__icontains=q)
            | Q(phone__icontains=q)
        )

    if account_type in ("personal", "professional"):
        qs = qs.filter(account_type=account_type)

    if staff in ("1", "0"):
        qs = qs.filter(is_staff=(staff == "1"))

    if active in ("1", "0"):
        qs = qs.filter(is_active=(active == "1"))

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    return _dash_render(
        request,
        "accounts/dash_pages/crud/users_list.html",
        {
            "page_obj": page_obj,
            "q": q,
            "account_type": account_type,
            "staff": staff,
            "active": active,
        },
    )


@staff_required
def dash_crud_users_edit(request, pk):
    u = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = AdminUserUpdateForm(request.POST, request.FILES, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, "User updated.")
            return redirect("accounts:dash_crud_users_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = AdminUserUpdateForm(instance=u)

    return _dash_render(
        request,
        "accounts/dash_pages/crud/users_edit.html",
        {"form": form, "target_user": u},
    )


@staff_required
def dash_crud_users_toggle_active(request, pk):
    if request.method != "POST":
        return redirect("accounts:dash_crud_users_list")

    u = get_object_or_404(User, pk=pk)

    # don’t let staff deactivate themselves by accident
    if u.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account here.")
        return redirect("accounts:dash_crud_users_list")

    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    messages.success(request, f"User is now {'active' if u.is_active else 'inactive'}.")
    return redirect("accounts:dash_crud_users_list")


@staff_required
def dash_crud_users_toggle_staff(request, pk):
    if request.method != "POST":
        return redirect("accounts:dash_crud_users_list")

    u = get_object_or_404(User, pk=pk)

    # don’t let staff demote themselves by accident
    if u.pk == request.user.pk:
        messages.error(request, "You cannot change your own staff status here.")
        return redirect("accounts:dash_crud_users_list")

    u.is_staff = not u.is_staff
    u.save(update_fields=["is_staff"])
    messages.success(request, f"User is now {'staff' if u.is_staff else 'not staff'}.")
    return redirect("accounts:dash_crud_users_list")