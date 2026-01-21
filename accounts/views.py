from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.db.models import Avg, Count
from django.contrib.auth import get_user_model
import calendar
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
from .models import Profession, AccountPhoto, ProfessionalPhoto, AudioAcapellaCover, VideoAcapellaCover, Review

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

    # tab support
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

        # Show locked/accepted bookings for this professional
        events_qs = (
            Event.objects
            .select_related("accepted_thread", "accepted_thread__professional", "created_by")
            .filter(is_locked=True, accepted_thread__professional=prof)
        )

        # professional avatar for background use (optional)
        avatar_url = ""
        if getattr(prof, "profile_picture", None):
            try:
                avatar_url = prof.profile_picture.url
            except Exception:
                avatar_url = ""

        booked_map = {}  # date -> {"avatar_url": "", "ranges": [...]}

        for e in events_qs:
            if not e.start_datetime or not e.end_datetime:
                continue

            start_local = timezone.localtime(e.start_datetime)
            end_local = timezone.localtime(e.end_datetime)
            d1 = start_local.date()
            d2 = end_local.date()

            # ✅ accepted pro info (for locked event)
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

                    # ✅ for modal display
                    "accepted_name": accepted_name,
                    "accepted_avatar": accepted_avatar,
                })

        # busy times (read-only)
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
def profile_edit_view(request):
    user = request.user

    if request.method == "POST":
        form = AccountsProfileForm(request.POST, request.FILES, instance=user)

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
            for f in photos_form.cleaned_data["normal_images"]:
                AccountPhoto.objects.create(user=user, image=f)

            # Professional photos
            for f in professional_form.cleaned_data["professional_images"]:
                ProfessionalPhoto.objects.create(user=user, image=f)

            # Audio acapella covers
            for f in audio_form.cleaned_data["audio_files"]:
                AudioAcapellaCover.objects.create(user=user, audio_file=f)

            # Video acapella covers
            for f in video_form.cleaned_data["video_files"]:
                VideoAcapellaCover.objects.create(user=user, video_file=f)

            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")

        messages.error(request, "Please correct the errors below.")
    else:
        form = AccountsProfileForm(instance=user)
        photos_form = NormalPhotosUploadForm()
        professional_form = ProfessionalPhotosUploadForm()
        audio_form = AudioCoversUploadForm()
        video_form = VideoCoversUploadForm()

    return render(
        request,
        "accounts/profile_edit.html",
        {
            "form": form,
            "photos_form": photos_form,
            "professional_form": professional_form,
            "audio_form": audio_form,
            "video_form": video_form,
        },
    )
@login_required
def create_review_view(request, pk):
    prof = get_object_or_404(User, pk=pk, account_type="professional", is_active=True)

    if prof.pk == request.user.pk:
        messages.error(request, "You cannot review your own profile.")
        return redirect("accounts:profile_detail", pk=prof.pk)

    # prevent duplicates (enforced by DB constraint too)
    if Review.objects.filter(professional=prof, reviewer=request.user).exists():
        messages.error(request, "You already left a review for this profile.")
        return redirect("accounts:profile_detail", pk=prof.pk)

    if request.method != "POST":
        return redirect("accounts:profile_detail", pk=prof.pk)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.professional = prof
        review.reviewer = request.user
        review.save()
        messages.success(request, "Review submitted successfully.")
    else:
        messages.error(request, "Please correct the errors in your review.")

    return redirect("accounts:profile_detail", pk=prof.pk)

def register_view(request):
    if request.method == "POST":
        form = AccountsRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully. Welcome!")
            return redirect("accounts:profile")
        messages.error(request, "Please correct the errors below.")
    else:
        form = AccountsRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        messages.success(self.request, "You are now logged in.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid credentials. Please try again.")
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
            messages.success(request, f"Profession '{prof.name}' created successfully.")
            return redirect("accounts:profession_create")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProfessionForm()

    return render(request, "accounts/profession_create.html", {"form": form})


@login_required
def profession_tree_view(request):
    professions = list(
        Profession.objects.all()
        .select_related("parent")
        .order_by("name")
    )

    children_map = {}
    for p in professions:
        children_map.setdefault(p.parent_id, []).append(p)

    def attach(node):
        node.tree_children = children_map.get(node.id, [])  # ✅ not "children"
        for c in node.tree_children:
            attach(c)

    roots = children_map.get(None, [])
    for r in roots:
        attach(r)

    return render(request, "accounts/profession_tree.html", {"roots": roots})

