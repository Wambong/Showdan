from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .forms import EventForm, EventCategoryForm
from django.utils import timezone
from .models import Event, OfferThread, OfferMessage, EventCategory
from django.db.models import Count, Q, Min, Max
from decimal import Decimal, InvalidOperation

from accounts.models import Profession

def _build_profession_tree_options():
    """
    Returns a list of tuples: (id, label_with_indent)
    where children are indented under their parents.
    """
    all_items = list(Profession.objects.select_related("parent").all())

    children_map = {}
    roots = []

    for p in all_items:
        pid = p.parent_id
        if pid is None:
            roots.append(p)
        children_map.setdefault(pid, []).append(p)

    # Keep descendants under their parent, but sort siblings by name.
    for pid, items in children_map.items():
        items.sort(key=lambda x: (x.name or "").lower())
    roots.sort(key=lambda x: (x.name or "").lower())

    out = []

    def walk(node, depth):
        indent = "\u00A0" * (depth * 4)  # 4 non-breaking spaces per level
        out.append((node.id, f"{indent}{node.name}"))
        for ch in children_map.get(node.id, []):
            walk(ch, depth + 1)

    for r in roots:
        walk(r, 0)

    return out


def events_list_view(request):
    # ----------------------------
    # show (upcoming/past/all)
    # ----------------------------
    show = (request.GET.get("show") or "upcoming").strip()
    now = timezone.now()

    base = (
        Event.objects
        .filter(is_posted=True)
        .select_related("event_type", "currency", "created_by")
        .prefetch_related("required_professions")
        .annotate(offers_received_count=Count("offer_threads", distinct=True))
    )

    if show == "past":
        base = base.filter(end_datetime__lt=now)
        title = "Past events"
        order_by = "-start_datetime"
    elif show == "all":
        title = "All events"
        order_by = "-start_datetime"
    else:
        show = "upcoming"
        base = base.filter(end_datetime__gte=now)
        title = "Upcoming events"
        order_by = "start_datetime"

    # ----------------------------
    # GET params (filters)
    # ----------------------------
    q = (request.GET.get("q") or "").strip()
    category_id = (request.GET.get("category") or "").strip()        # event_type
    profession_id = (request.GET.get("profession") or "").strip()    # required_professions
    country = (request.GET.get("country") or "").strip()
    city = (request.GET.get("city") or "").strip()
    location = (request.GET.get("location") or "").strip()
    near_me = (request.GET.get("near_me") or "") == "1"

    min_budget_raw = (request.GET.get("min_budget") or "").strip()
    max_budget_raw = (request.GET.get("max_budget") or "").strip()

    # We'll filter on this
    qs = base

    # ----------------------------
    # Search (free text)
    # ----------------------------
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(location__icontains=q) |
            Q(city__icontains=q) |
            Q(country__icontains=q) |
            Q(created_by__city__icontains=q) |
            Q(created_by__country__icontains=q) |
            Q(event_type__name__icontains=q) |
            Q(required_professions__name__icontains=q)
        )

    # ----------------------------
    # Category (EventCategory)
    # ----------------------------
    if category_id.isdigit():
        qs = qs.filter(event_type__id=int(category_id))

    # ----------------------------
    # Required profession (M2M)
    # ----------------------------
    if profession_id.isdigit():
        qs = qs.filter(required_professions__id=int(profession_id))

    # ----------------------------
    # Location filters (Event OR creator fallback)
    # ----------------------------
    if country:
        qs = qs.filter(
            Q(country__icontains=country) |
            Q(created_by__country__icontains=country)
        )

    if city:
        qs = qs.filter(
            Q(city__icontains=city) |
            Q(created_by__city__icontains=city)
        )

    if location:
        qs = qs.filter(location__icontains=location)

    # ----------------------------
    # Near me (Event OR creator fallback)
    # ----------------------------
    if near_me and request.user.is_authenticated:
        u_country = (getattr(request.user, "country", "") or "").strip()
        u_city = (getattr(request.user, "city", "") or "").strip()

        if u_country and u_city:
            qs = qs.filter(
                Q(country__iexact=u_country, city__iexact=u_city) |
                Q(created_by__country__iexact=u_country, created_by__city__iexact=u_city)
            )
        elif u_country:
            qs = qs.filter(
                Q(country__iexact=u_country) |
                Q(created_by__country__iexact=u_country)
            )
        elif u_city:
            qs = qs.filter(
                Q(city__iexact=u_city) |
                Q(created_by__city__iexact=u_city)
            )
        # if both empty -> do nothing

    # ----------------------------
    # Budget range filter (event_budget)
    # IMPORTANT: exclude NULL budgets from comparisons so it doesn't wipe results
    # ----------------------------
    def to_decimal(s: str):
        if not s:
            return None
        try:
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return None

    min_budget = to_decimal(min_budget_raw)
    max_budget = to_decimal(max_budget_raw)

    if min_budget is not None:
        qs = qs.filter(event_budget__isnull=False, event_budget__gte=min_budget)

    if max_budget is not None:
        qs = qs.filter(event_budget__isnull=False, event_budget__lte=max_budget)

    qs = qs.distinct().order_by(order_by)

    # ----------------------------
    # Options for UI
    # ----------------------------
    categories = EventCategory.objects.all().order_by("path")

    # Professions: indented tree options (tuples: (id, label))
    profession_options = _build_profession_tree_options()

    # Slider bounds: compute from base (stable), not filtered qs
    base_for_bounds = base
    bounds = base_for_bounds.aggregate(bmin=Min("event_budget"), bmax=Max("event_budget"))
    bmin = bounds["bmin"] if bounds["bmin"] is not None else 0
    bmax = bounds["bmax"] if bounds["bmax"] is not None else 600
    if int(bmax) <= int(bmin):
        bmax = int(bmin) + 1

    return render(request, "events/events_list.html", {
        "events": qs,
        "title": title,
        "show": show,

        # UI options
        "categories": categories,
        "profession_options": profession_options,

        # filter state
        "f_q": q,
        "f_category": category_id,
        "f_profession": profession_id,
        "f_country": country,
        "f_city": city,
        "f_location": location,
        "f_min_budget": min_budget_raw,
        "f_max_budget": max_budget_raw,
        "f_near_me": near_me,

        # slider bounds
        "bmin": int(bmin),
        "bmax": int(bmax),
    })

@login_required
def event_detail_view(request, event_id):
    e = get_object_or_404(
        Event.objects.select_related(
            "created_by",
            "currency",
            "event_type",
            "accepted_thread",
            "accepted_thread__professional",
        ).prefetch_related("required_professions"),
        id=event_id,
    )

    # For display (local time)
    start_local = timezone.localtime(e.start_datetime) if e.start_datetime else None
    end_local = timezone.localtime(e.end_datetime) if e.end_datetime else None

    # Helpful booleans
    is_creator = (e.created_by_id == request.user.id)
    is_pro = getattr(request.user, "account_type", None) == "professional"

    accepted_pro = None
    accepted_pro_avatar = ""
    if e.is_locked and e.accepted_thread and e.accepted_thread.professional:
        accepted_pro = e.accepted_thread.professional
        pic = getattr(accepted_pro, "profile_picture", None)
        if pic:
            try:
                accepted_pro_avatar = pic.url
            except Exception:
                accepted_pro_avatar = ""

    return render(request, "events/event_detail.html", {
        "e": e,
        "start_local": start_local,
        "end_local": end_local,
        "is_creator": is_creator,
        "is_pro": is_pro,
        "accepted_pro": accepted_pro,
        "accepted_pro_avatar": accepted_pro_avatar,
    })
@login_required
def category_create_view(request):
    if request.method == "POST":
        form = EventCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Event category created successfully.")
            return redirect("events:category_create")
        messages.error(request, "Please correct the errors below.")
    else:
        form = EventCategoryForm()

    return render(request, "events/category_create.html", {"form": form})


@login_required
def event_create_view(request):
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user  # ✅ important
            event.is_posted = True
            if not event.currency and request.user.currency:
                event.currency = request.user.currency

            event.save()
            form.save_m2m()

            messages.success(request, "Event created successfully.")
            return redirect("events:list")
    else:
        form = EventForm()

    return render(request, "events/event_create.html", {"form": form})



