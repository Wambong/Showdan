from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import *
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
User = get_user_model()

from .crud_forms import *
from .models import *
from events.models import EventCategory
from django.middleware.csrf import get_token

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
            "media_cfg_professional": {"kind":"professional","title":"Professional photos","item_type":"image"},
            "media_cfg_normal": {"kind":"normal","title":"Normal photos","item_type":"image"},
            "media_cfg_audio": {"kind":"audio","title":"Audio Acapella Covers","item_type":"audio"},
            "media_cfg_video": {"kind":"video","title":"Video Acapella Covers","item_type":"video"},
        },
    )

def _build_profession_tree_options():
    """
    Returns list of tuples: (id, label_with_indent) in parent->children order.
    Keeps descendants under their parent (no confusing global alpha ordering).
    """
    all_items = list(Profession.objects.select_related("parent").all())

    children_map = {}
    roots = []

    for p in all_items:
        pid = p.parent_id
        if pid is None:
            roots.append(p)
        children_map.setdefault(pid, []).append(p)

    # sort siblings by name (but keep tree structure)
    for pid, items in children_map.items():
        items.sort(key=lambda x: (x.name or "").lower())
    roots.sort(key=lambda x: (x.name or "").lower())

    out = []

    def walk(node, depth):
        indent = "\u00A0" * (depth * 4)  # NBSP indentation works in HTML
        out.append((node.id, f"{indent}{node.name}"))
        for ch in children_map.get(node.id, []):
            walk(ch, depth + 1)

    for r in roots:
        walk(r, 0)

    return out


@login_required
@require_http_methods(["GET", "POST"])
def dash_switch_profile(request):
    u = request.user

    # Step selector (no JS): user clicks a link that sets ?target=...
    target = (request.GET.get("target") or "").strip().lower()
    if target not in ("personal", "professional"):
        target = ""  # means "no selection yet"

    current = getattr(u, "account_type", "personal") or "personal"

    profession_options = _build_profession_tree_options()
    selected_prof_ids = set(u.professions.values_list("id", flat=True))

    if request.method == "POST":
        target = (request.POST.get("target") or "").strip().lower()

        if target not in ("personal", "professional"):
            messages.error(request, _("Invalid target account type."))
            return redirect("accounts:switch_profile")

        # Switching to personal
        if target == "personal":
            u.account_type = "personal"
            u.save(update_fields=["account_type"])

            # optional but recommended: clear professions when personal
            u.professions.clear()

            messages.success(request, _("Switched to Personal profile."))
            return redirect("accounts:dash_home")

        # Switching to professional
        prof_ids = request.POST.getlist("professions")
        prof_ids_int = [int(x) for x in prof_ids if str(x).isdigit()]

        if not prof_ids_int:
            # must pick professions when becoming professional
            messages.error(request, _("Please select at least one profession to switch to Professional."))
            # stay on the same page (target=professional)
            return redirect(f"{request.path}?target=professional")

        u.account_type = "professional"
        u.save(update_fields=["account_type"])
        u.professions.set(prof_ids_int)

        messages.success(request, _("Switched to Professional profile."))
        return redirect("accounts:dash_home")

    return _dash_render(
        request,
        "accounts/dash_pages/switch_profile.html",
        {
            "u": u,
            "current": current,
            "target": target,
            "profession_options": profession_options,
            "selected_prof_ids": selected_prof_ids,
        },
    )

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

        messages.error(request, _("Please correct the errors below."))

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
    items = (
        FavoriteProfessional.objects
        .filter(user=request.user)
        .select_related("professional")
        .order_by("-created_at")
    )
    return _dash_render(request, "accounts/dash_pages/favorites.html", {"u": u,"items": items})
@login_required
def favorite_add_view(request, pro_id):
    pro = get_object_or_404(User, pk=pro_id, is_active=True, account_type="professional")

    if pro.id == request.user.id:
        messages.error(request, _("You cannot favorite yourself."))
        return redirect("accounts:profile_detail", pro_id)

    FavoriteProfessional.objects.get_or_create(user=request.user, professional=pro)
    messages.success(request, "Added to favorites.")
    return redirect(request.META.get("HTTP_REFERER", "accounts:favorites"))


@login_required
def favorite_remove_view(request, pro_id):
    if request.method != "POST":
        # allow normal non-htmx link fallback if you want:
        FavoriteProfessional.objects.filter(user=request.user, professional_id=pro_id).delete()
        messages.success(request, _("Removed from favorites."))
        return redirect("accounts:favorites")

    FavoriteProfessional.objects.filter(user=request.user, professional_id=pro_id).delete()
    messages.success(request, _("Removed from favorites."))
    return dash_favorites(request)  # re-render favorites into dash main card

@login_required
def favorite_toggle_view(request, pro_id):
    pro = get_object_or_404(User, pk=pro_id, is_active=True)

    # Prevent favoriting yourself (optional)
    if pro.id == request.user.id:
        if request.headers.get("HX-Request") == "true":
            # return the unchanged button
            token = get_token(request)
            return HttpResponse(
                f"""
                <div id="favBtnWrap">
                  <form method="post" action="/accounts/favorites/toggle/{pro.id}/"
                        hx-post="/accounts/favorites/toggle/{pro.id}/"
                        hx-target="#favBtnWrap" hx-swap="outerHTML">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{token}">
                    <button class="btn btn-sm btn-outline-light" type="submit" aria-label="Toggle favorite">♡</button>
                  </form>
                </div>
                """,
                content_type="text/html",
            )
        return redirect("accounts:profile_detail", pro.id)

    # Toggle
    obj = FavoriteProfessional.objects.filter(user=request.user, professional=pro).first()
    if obj:
        obj.delete()
        is_favorite = False
    else:
        FavoriteProfessional.objects.create(user=request.user, professional=pro)
        is_favorite = True

    # If HTMX: return only the updated button wrapper
    if request.headers.get("HX-Request") == "true":
        token = get_token(request)
        heart = "♥" if is_favorite else "♡"
        return HttpResponse(
            f"""
            <div id="favBtnWrap">
              <form method="post" action="/accounts/favorites/toggle/{pro.id}/"
                    hx-post="/accounts/favorites/toggle/{pro.id}/"
                    hx-target="#favBtnWrap" hx-swap="outerHTML">
                <input type="hidden" name="csrfmiddlewaretoken" value="{token}">
                <button class="btn btn-sm btn-outline-light" type="submit" aria-label="Toggle favorite">{heart}</button>
              </form>
            </div>
            """,
            content_type="text/html",
        )

    # Normal fallback: redirect back to profile detail page
    return redirect("accounts:profile_detail", pro.id)

@login_required
def dash_currency(request):
    u = request.user

    if request.method == "POST":
        form = DashCurrencyForm(request.POST, instance=u)
        if form.is_valid():
            u.currency = form.cleaned_data["currency"]
            u.save(update_fields=["currency"])
            messages.success(request, _("Currency updated."))
        else:
            messages.error(request, _("Please correct the errors below."))
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
            messages.success(request, _("Languages updated."))
        else:
            messages.error(request, _("Please correct the errors below."))
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
        messages.success(request, _("Profession created."))
        return redirect("accounts:dash_crud_profession_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New profession"})

@staff_member_required
def dash_crud_profession_edit(request, pk):
    obj = get_object_or_404(Profession, pk=pk)
    form = ProfessionForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profession updated."))
        return redirect("accounts:dash_crud_profession_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit profession"})

@staff_member_required
def dash_crud_profession_delete(request, pk):
    obj = get_object_or_404(Profession, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, _("Profession deleted."))
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
        messages.success(request, _("Event category created."))
        return redirect("accounts:dash_crud_eventcategory_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New event category"})

@staff_member_required
def dash_crud_eventcategory_edit(request, pk):
    obj = get_object_or_404(EventCategory, pk=pk)
    form = EventCategoryForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Event category updated."))
        return redirect("accounts:dash_crud_eventcategory_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit event category"})

@staff_member_required
def dash_crud_eventcategory_delete(request, pk):
    obj = get_object_or_404(EventCategory, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, _("Event category deleted."))
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
        messages.success(request, _("Language created."))
        return redirect("accounts:dash_crud_language_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New language"})

@staff_member_required
def dash_crud_language_edit(request, pk):
    obj = get_object_or_404(Language, pk=pk)
    form = LanguageForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Language updated."))
        return redirect("accounts:dash_crud_language_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit language"})

@staff_member_required
def dash_crud_language_delete(request, pk):
    obj = get_object_or_404(Language, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, _("Language deleted."))
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
        messages.success(request, _("Currency created."))
        return redirect("accounts:dash_crud_currency_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New currency"})

@staff_member_required
def dash_crud_currency_edit(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    form = CurrencyForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Currency updated."))
        return redirect("accounts:dash_crud_currency_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit currency"})

@staff_member_required
def dash_crud_currency_delete(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, _("Currency deleted."))
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
        messages.success(request, _("Exchange rate created."))
        return redirect("accounts:dash_crud_exchangerate_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "New exchange rate"})

@staff_member_required
def dash_crud_exchangerate_edit(request, pk):
    obj = get_object_or_404(ExchangeRate, pk=pk)
    form = ExchangeRateForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Exchange rate updated."))
        return redirect("accounts:dash_crud_exchangerate_list")
    return _dash_render(request, "accounts/dash_pages/crud/form.html", {"form": form, "title": "Edit exchange rate"})

@staff_member_required
def dash_crud_exchangerate_delete(request, pk):
    obj = get_object_or_404(ExchangeRate, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, _("Exchange rate deleted."))
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
            messages.success(request, _("User updated."))
            return redirect("accounts:dash_crud_users_list")
        messages.error(request, _("Please correct the errors below."))
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


def _is_hx(request):
    return request.headers.get("HX-Request") == "true"


def _media_config(kind: str):
    """
    Returns config for each media kind.
    """
    kind = (kind or "").strip().lower()

    if kind == "professional":
        return {
            "kind": "professional",
            "title": "Professional photos",
            "model": ProfessionalPhoto,
            "file_field": "image",  # model field name
            "upload_form": ProfessionalPhotosUploadForm,
            "upload_field": "professional_images",  # form field name
            "item_type": "image",
        }

    if kind == "normal":
        return {
            "kind": "normal",
            "title": "Normal photos",
            "model": AccountPhoto,
            "file_field": "image",
            "upload_form": NormalPhotosUploadForm,
            "upload_field": "normal_images",
            "item_type": "image",
        }

    if kind == "audio":
        return {
            "kind": "audio",
            "title": "Audio Acapella Covers",
            "model": AudioAcapellaCover,
            "file_field": "audio_file",
            "upload_form": AudioCoversUploadForm,
            "upload_field": "audio_files",
            "item_type": "audio",
        }

    if kind == "video":
        return {
            "kind": "video",
            "title": "Video Acapella Covers",
            "model": VideoAcapellaCover,
            "file_field": "video_file",
            "upload_form": VideoCoversUploadForm,
            "upload_field": "video_files",
            "item_type": "video",
        }

    return None


@login_required
def dash_media_section_view(request, kind):
    """
    Returns the VIEW block for a section (used for cancel + after save).
    HTMX: returns partial HTML. Normal browser: redirect to dashboard home.
    """
    cfg = _media_config(kind)
    if not cfg:
        return HttpResponseBadRequest("Invalid media kind")

    if not _is_hx(request):
        return redirect("accounts:dash_home")

    items = cfg["model"].objects.filter(user=request.user).order_by("-id")

    return render(request, "accounts/dash_pages/partials/media_section.html", {
        "cfg": cfg,
        "items": items,
    })


@login_required
def dash_media_section_edit_view(request, kind):
    """
    GET: returns edit form partial for the section.
    POST: handles delete + upload, then returns the view partial.
    """
    cfg = _media_config(kind)
    if not cfg:
        return HttpResponseBadRequest("Invalid media kind")

    if not _is_hx(request):
        return redirect("accounts:dash_home")

    Model = cfg["model"]
    upload_form_cls = cfg["upload_form"]
    upload_field = cfg["upload_field"]
    file_field = cfg["file_field"]

    items = Model.objects.filter(user=request.user).order_by("-id")

    if request.method == "POST":
        form = upload_form_cls(request.POST, request.FILES)

        # 1) Delete selected
        delete_ids = [x for x in request.POST.getlist("delete_ids") if str(x).isdigit()]
        if delete_ids:
            Model.objects.filter(user=request.user, id__in=delete_ids).delete()

        # 2) Upload new files (optional)
        if form.is_valid():
            files = request.FILES.getlist(upload_field)  # multiple file field
            for f in files:
                obj = Model(user=request.user)
                setattr(obj, file_field, f)
                obj.save()

            messages.success(request, _("Saved."))
        else:
            # Form invalid: stay in edit mode and show errors
            return render(request, "accounts/dash_pages/partials/media_edit.html", {
                "cfg": cfg,
                "items": items,
                "form": form,
            })

        # return updated VIEW block
        items = Model.objects.filter(user=request.user).order_by("-id")
        return render(request, "accounts/dash_pages/partials/media_section.html", {
            "cfg": cfg,
            "items": items,
        })

    # GET: show edit form
    form = upload_form_cls()
    return render(request, "accounts/dash_pages/partials/media_edit.html", {
        "cfg": cfg,
        "items": items,
        "form": form,
    })



def news_list_view(request):
    qs = NewsPost.objects.filter(is_published=True).order_by("-published_at", "-created_at")
    return render(request, "accounts/news_list.html", {"items": qs})


def news_detail_view(request, slug):
    item = get_object_or_404(NewsPost, slug=slug, is_published=True)
    return render(request, "accounts/news_detail.html", {"item": item})

def news_detail_view(request, slug):
    item = get_object_or_404(NewsPost, slug=slug, is_published=True)

    if request.user.is_authenticated:
        NewsRead.objects.update_or_create(
            user=request.user,
            post=item,
            defaults={"read_at": timezone.now()},
        )

    return render(request, "accounts/news_detail.html", {"item": item})
@staff_required
def dash_crud_news_list(request):
    items = NewsPost.objects.all().order_by("-created_at")
    return _dash_render(request, "accounts/dash_pages/crud/news_list.html", {"items": items})


@staff_required
def dash_crud_news_create(request):
    if request.method == "POST":
        form = NewsPostForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, _("News post created."))
            return redirect("accounts:dash_crud_news_list")
        messages.error(request, _("Please correct the errors."))
    else:
        form = NewsPostForm()

    return _dash_render(request, "accounts/dash_pages/crud/news_form.html", {"form": form, "mode": "create"})


@staff_required
def dash_crud_news_edit(request, pk):
    obj = get_object_or_404(NewsPost, pk=pk)
    if request.method == "POST":
        form = NewsPostForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, _("News post updated."))
            return redirect("accounts:dash_crud_news_list")
        messages.error(request, _("Please correct the errors."))
    else:
        form = NewsPostForm(instance=obj)

    return _dash_render(request, "accounts/dash_pages/crud/news_form.html", {"form": form, "mode": "edit", "obj": obj})


@staff_required
def dash_crud_news_delete(request, pk):
    obj = get_object_or_404(NewsPost, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, _("News post deleted."))
        return redirect("accounts:dash_crud_news_list")

    return _dash_render(request, "accounts/dash_pages/crud/news_confirm_delete.html", {"obj": obj})

