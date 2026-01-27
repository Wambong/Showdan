from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.db.models import Avg, Count
from django.contrib.auth import get_user_model
import calendar
from django.utils.translation import gettext_lazy as _
from django.utils.text import format_lazy
from datetime import date, datetime, timedelta
from django.utils import timezone
from .forms import (
    AccountsRegistrationForm,
    ProfessionForm,
    AccountsProfileForm,
    NormalPhotosUploadForm,
    ProfessionalPhotosUploadForm,
    AudioCoversUploadForm,
    VideoCoversUploadForm,
    ReviewForm
)

User = get_user_model()
from events.models import Event, BusyTime
from .models import Profession, AccountPhoto, ProfessionalPhoto, AudioAcapellaCover, VideoAcapellaCover, Review, FavoriteProfessional

@login_required
def dashboard_view(request):
    u = request.user

    ctx = {
        "u": u,
        "is_pro": getattr(u, "account_type", None) == "professional",
    }
    return render(request, "accounts/dashboard.html", ctx)
def month_start_end(year: int, month: int):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    last = date(year, month, last_day)
    return first, last


def daterange(d1: date, d2: date):
    cur = d1
    while cur <= d2:
        yield cur
        cur += timedelta(days=1)

def public_profile_detail_view(request, pk):
    prof = get_object_or_404(User, pk=pk, account_type="professional", is_active=True)

    # ✅ Favorite state
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = FavoriteProfessional.objects.filter(
            user=request.user,
            professional=prof
        ).exists()

    tab = request.GET.get("tab", "overview")
    valid_tabs = {"overview", "calendar"}
    if tab not in valid_tabs:
        tab = "overview"

    normal_photos = AccountPhoto.objects.filter(user=prof).order_by("-id")
    professional_photos = ProfessionalPhoto.objects.filter(user=prof).order_by("-id")
    audio_covers = AudioAcapellaCover.objects.filter(user=prof).order_by("-id")
    video_covers = VideoAcapellaCover.objects.filter(user=prof).order_by("-id")

    reviews = Review.objects.filter(professional=prof).select_related("reviewer")
    stats = reviews.aggregate(avg=Avg("rating"), cnt=Count("id"))
    avg_rating = stats["avg"] or 0
    review_count = stats["cnt"] or 0

    review_form = None
    can_review = False
    existing_review = None

    if request.user.is_authenticated and request.user.pk != prof.pk:
        can_review = True
        existing_review = Review.objects.filter(professional=prof, reviewer=request.user).first()
        if not existing_review:
            review_form = ReviewForm()

    # ✅ Similar professionals (same professions if possible)
    base_similar = (
        User.objects
        .filter(account_type="professional", is_active=True)
        .exclude(pk=prof.pk)
        .prefetch_related("professions")
        .select_related("currency")
        .annotate(avg_rating=Avg("reviews_received__rating"))
        .annotate(review_count=Count("reviews_received"))
    )

    prof_profession_ids = list(prof.professions.values_list("id", flat=True))

    if prof_profession_ids:
        pros = (
            base_similar
            .filter(professions__id__in=prof_profession_ids)
            .distinct()
            .order_by("-id")[:8]
        )
    else:
        # fallback: show some professionals anyway
        pros = base_similar.order_by("-id")[:8]

    # ===============================
    # Calendar tab context (read-only)
    # ===============================
    calendar_ctx = {}
    if tab == "calendar":
        today = timezone.localdate()
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))

        first_day, last_day = month_start_end(year, month)

        cal = calendar.Calendar(firstweekday=0)  # Monday
        weeks = cal.monthdatescalendar(year, month)

        events_qs = (
            Event.objects
            .select_related("accepted_thread", "accepted_thread__professional", "created_by")
            .filter(is_locked=True, accepted_thread__professional=prof)
        )

        avatar_url = ""
        if getattr(prof, "profile_picture", None):
            try:
                avatar_url = prof.profile_picture.url
            except Exception:
                avatar_url = ""

        booked_map = {}

        for e in events_qs:
            if not e.start_datetime or not e.end_datetime:
                continue

            start_local = timezone.localtime(e.start_datetime)
            end_local = timezone.localtime(e.end_datetime)
            d1 = start_local.date()
            d2 = end_local.date()

            accepted_name = ""
            accepted_avatar = ""
            if e.is_locked and getattr(e, "accepted_thread", None) and getattr(e.accepted_thread, "professional", None):
                ap = e.accepted_thread.professional
                accepted_name = f"{ap.first_name} {ap.last_name}"
                if getattr(ap, "profile_picture", None):
                    try:
                        accepted_avatar = ap.profile_picture.url
                    except Exception:
                        accepted_avatar = ""

            for d in daterange(d1, d2):
                booked_map.setdefault(d, {"avatar_url": avatar_url, "ranges": []})

                is_start = (d == d1)
                is_end = (d == d2)

                label = ""
                if is_start and is_end:
                    label = f"{start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')}"
                elif is_start:
                    label = f"{start_local.strftime('%H:%M')} →"
                elif is_end:
                    label = f"→ {end_local.strftime('%H:%M')}"

                booked_map[d]["ranges"].append({
                    "event_id": e.id,
                    "name": e.name,
                    "is_start": is_start,
                    "is_end": is_end,
                    "label": label,
                    "is_locked": bool(e.is_locked),
                    "accepted_name": accepted_name,
                    "accepted_avatar": accepted_avatar,
                })

        busy_qs = BusyTime.objects.filter(
            user=prof,
            start_datetime__date__lte=last_day,
            end_datetime__date__gte=first_day
        )

        busy_map = {}
        for b in busy_qs:
            s = timezone.localtime(b.start_datetime)
            e = timezone.localtime(b.end_datetime)
            for d in daterange(s.date(), e.date()):
                busy_map.setdefault(d, []).append({
                    "is_all_day": b.is_all_day,
                    "start": s.strftime("%H:%M"),
                    "end": e.strftime("%H:%M"),
                })

        prev_month = (date(year, month, 1) - timedelta(days=1)).replace(day=1)
        next_month = (date(year, month, 28) + timedelta(days=10)).replace(day=1)

        calendar_ctx = {
            "weeks": weeks,
            "year": year,
            "month": month,
            "month_name": date(year, month, 1).strftime("%B"),
            "prev_year": prev_month.year,
            "prev_month": prev_month.month,
            "next_year": next_month.year,
            "next_month": next_month.month,
            "today": today,
            "booked_map": booked_map,
            "busy_map": busy_map,
            "avatar_url": avatar_url,
        }

    return render(
        request,
        "accounts/profile_detail.html",
        {
            "prof": prof,
            "tab": tab,
            "is_favorite": is_favorite,

            "normal_photos": normal_photos,
            "professional_photos": professional_photos,
            "audio_covers": audio_covers,
            "video_covers": video_covers,

            "reviews": reviews,
            "avg_rating": avg_rating,
            "review_count": review_count,
            "review_form": review_form,
            "can_review": can_review,
            "existing_review": existing_review,

            # ✅ NEW
            "pros": pros,

            **calendar_ctx,
        },
    )

def profile_media_hub_view(request, pk):
    prof = get_object_or_404(User, pk=pk, account_type="professional", is_active=True)

    tab = request.GET.get("tab", "studio")
    valid_tabs = {"studio", "work", "audio", "video"}
    if tab not in valid_tabs:
        tab = "studio"

    context = {
        "prof": prof,
        "tab": tab,
        "tabs": [
            ("studio", "Studio photos"),
            ("work", "Work photos"),
            ("audio", "Audio"),
            ("video", "Video"),
        ],
    }

    if tab == "studio":
        context["items"] = ProfessionalPhoto.objects.filter(user=prof).order_by("-id")
        context["kind"] = "photos"
        context["title"] = "Studio photos"

    elif tab == "work":
        context["items"] = AccountPhoto.objects.filter(user=prof).order_by("-id")
        context["kind"] = "photos"
        context["title"] = "Work photos"

    elif tab == "audio":
        context["items"] = AudioAcapellaCover.objects.filter(user=prof).order_by("-id")
        context["kind"] = "audio"
        context["title"] = "Audio"

    elif tab == "video":
        context["items"] = VideoAcapellaCover.objects.filter(user=prof).order_by("-id")
        context["kind"] = "video"
        context["title"] = "Video"

    return render(request, "accounts/profile_media.html", context)

@login_required
def create_review_view(request, pk):
    prof = get_object_or_404(User, pk=pk, account_type="professional", is_active=True)

    if prof.pk == request.user.pk:
        messages.error(request, _("You cannot review your own profile."))
        return redirect("accounts:profile_detail", pk=prof.pk)

    # prevent duplicates (enforced by DB constraint too)
    if Review.objects.filter(professional=prof, reviewer=request.user).exists():
        messages.error(request, _("You already left a review for this profile."))
        return redirect("accounts:profile_detail", pk=prof.pk)

    if request.method != "POST":
        return redirect("accounts:profile_detail", pk=prof.pk)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.professional = prof
        review.reviewer = request.user
        review.save()
        messages.success(request, _("Review submitted successfully."))
    else:
        messages.error(request, _("Please correct the errors in your review."))

    return redirect("accounts:profile_detail", pk=prof.pk)

def register_view(request):
    if request.method == "POST":
        form = AccountsRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # ✅ authenticate so Django knows which backend to attach
            authed = authenticate(request, email=user.email, password=form.cleaned_data["password1"])
            if authed is not None:
                login(request, authed)
                messages.success(request, _("Account created successfully. Welcome!"))
                return redirect("accounts:dashboard")

            # fallback (shouldn't usually happen)
            messages.success(request, _("Account created. Please log in."))
            return redirect("accounts:login")

        messages.error(request, _("Please correct the errors below."))
    else:
        form = AccountsRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})



class AccountLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        messages.success(self.request, _("You are now logged in."))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Invalid credentials. Please try again."))
        return super().form_invalid(form)


class AccountLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        messages.success(request, "You have been logged out.")
        return super().dispatch(request, *args, **kwargs)


@login_required
def profile_view(request):
    return render(request, "accounts/profile.html")


def can_create_professions(user):
    return user.is_authenticated and (user.is_staff or user.account_type == "professional")

@user_passes_test(can_create_professions)
def profession_create_view(request):
    if request.method == "POST":
        form = ProfessionForm(request.POST)
        if form.is_valid():
            prof = form.save()
            messages.success(
                request,
                format_lazy(_("Profession “{name}” created successfully."), name=prof.name),
            )
            return redirect("accounts:profession_create")
        messages.error(request, _("Please correct the errors below."))
    else:
        form = ProfessionForm()

    return render(request, "accounts/profession_create.html", {"form": form})




