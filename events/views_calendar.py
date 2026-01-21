import calendar
from datetime import date, datetime, timedelta, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.urls import reverse
from .models import Event, BusyTime
from django.db import transaction

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

@login_required
def calendar_view(request):
    user = request.user
    today = timezone.localdate()

    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    hours = [f"{h:02d}" for h in range(24)]
    minutes = ["00", "15", "30", "45"]

    first_day, last_day = month_start_end(year, month)

    cal = calendar.Calendar(firstweekday=0)  # Monday
    weeks = cal.monthdatescalendar(year, month)

    is_pro = getattr(user, "account_type", None) == "professional"

    # ===============================
    # 1) Events to show on calendar
    # - Always show events CREATED by user
    # - If professional: also show events BOOKED by them (accepted_thread.professional=user)
    # ===============================
    creator_events = (
        Event.objects
        .select_related("currency", "created_by", "accepted_thread", "accepted_thread__professional")
        .filter(created_by=user)
    )

    booked_events = Event.objects.none()
    if is_pro:
        booked_events = (
            Event.objects
            .select_related("currency", "created_by", "accepted_thread", "accepted_thread__professional")
            .filter(is_locked=True, accepted_thread__professional=user)
        )

    booked_map = {}  # date -> {"avatar_url": "", "ranges": [...]}

    def ensure_day(d):
        booked_map.setdefault(d, {"avatar_url": "", "ranges": []})

    def safe_avatar(u):
        if not u:
            return ""
        pic = getattr(u, "profile_picture", None)
        if not pic:
            return ""
        try:
            return pic.url
        except Exception:
            return ""

    my_avatar_url = safe_avatar(user)

    # ---------- A) Creator events ----------
    # show name always; avatar only if locked (accepted professional)
    for e in creator_events:
        if not e.start_datetime or not e.end_datetime:
            continue

        start_local = timezone.localtime(e.start_datetime)
        end_local = timezone.localtime(e.end_datetime)
        d1 = start_local.date()
        d2 = end_local.date()

        accepted_avatar_url = ""
        if e.is_locked and e.accepted_thread and getattr(e.accepted_thread, "professional", None):
            accepted_avatar_url = safe_avatar(e.accepted_thread.professional)

        for d in daterange(d1, d2):
            ensure_day(d)

            # Only apply accepted avatar for locked events
            if accepted_avatar_url:
                booked_map[d]["avatar_url"] = accepted_avatar_url

            is_start = (d == d1)
            is_end = (d == d2)

            # label logic
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
                "source": "created",
            })

    # ---------- B) Professional accepted bookings ----------
    # show name; avatar is ALWAYS the professional's own avatar
    for e in booked_events:
        if not e.start_datetime or not e.end_datetime:
            continue

        start_local = timezone.localtime(e.start_datetime)
        end_local = timezone.localtime(e.end_datetime)
        d1 = start_local.date()
        d2 = end_local.date()

        for d in daterange(d1, d2):
            ensure_day(d)

            # only set avatar if not already set by a locked created event
            if my_avatar_url and not booked_map[d]["avatar_url"]:
                booked_map[d]["avatar_url"] = my_avatar_url

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
                "is_locked": True,
                "source": "booked",
            })

    # ===============================
    # 2) Busy times (unavailable)
    # ===============================
    busy_qs = BusyTime.objects.filter(
        user=user,
        start_datetime__date__lte=last_day,
        end_datetime__date__gte=first_day
    )

    busy_map = {}  # date -> [busy items]
    for b in busy_qs:
        s = timezone.localtime(b.start_datetime)
        e = timezone.localtime(b.end_datetime)
        for d in daterange(s.date(), e.date()):
            busy_map.setdefault(d, []).append({
                "is_all_day": b.is_all_day,
                "start": s.strftime("%H:%M"),
                "end": e.strftime("%H:%M"),
                "note": b.note,
            })

    # ===============================
    # POST: create busy time
    # ===============================
    if request.method == "POST":
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        mode = request.POST.get("busy_mode")  # all_day / timed

        if not start_date or not end_date:
            messages.error(request, "Please select at least one day.")
            return redirect("events:calendar")

        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        if ed < sd:
            sd, ed = ed, sd

        note = (request.POST.get("note") or "").strip()

        if mode == "timed":
            hh1 = request.POST.get("start_hour", "00")
            mm1 = request.POST.get("start_min", "00")
            hh2 = request.POST.get("end_hour", "00")
            mm2 = request.POST.get("end_min", "00")

            start_dt = timezone.make_aware(datetime.combine(sd, time(int(hh1), int(mm1))))
            end_dt = timezone.make_aware(datetime.combine(ed, time(int(hh2), int(mm2))))

            if end_dt <= start_dt:
                messages.error(request, "End time must be after start time.")
                return redirect("events:calendar")

            BusyTime.objects.create(
                user=user,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_all_day=False,
                note=note,
            )
        else:
            start_dt = timezone.make_aware(datetime.combine(sd, time(0, 0)))
            end_dt = timezone.make_aware(datetime.combine(ed, time(23, 59)))

            BusyTime.objects.create(
                user=user,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_all_day=True,
                note=note,
            )

        messages.success(request, "Busy time saved.")
        return redirect(f"{request.path}?year={year}&month={month}")

    # Month nav
    prev_month = (date(year, month, 1) - timedelta(days=1)).replace(day=1)
    next_month = (date(year, month, 28) + timedelta(days=10)).replace(day=1)

    return render(request, "events/calendar.html", {
        "hours": hours,
        "minutes": minutes,
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
        "is_professional": is_pro,
    })



@login_required
@transaction.atomic
def busytime_delete_day(request):
    if request.method != "POST":
        return redirect("events:calendar")

    day_str = request.POST.get("day")
    if not day_str:
        messages.error(request, "No day selected.")
        return redirect("events:calendar")

    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Invalid date.")
        return redirect("events:calendar")

    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(day, time(0, 0, 0)), tz)
    day_end = timezone.make_aware(datetime.combine(day, time(23, 59, 59)), tz)

    # Small buffer to avoid overlap when splitting
    left_end = day_start - timedelta(seconds=1)
    right_start = day_end + timedelta(seconds=1)

    qs = BusyTime.objects.filter(
        user=request.user,
        start_datetime__lte=day_end,
        end_datetime__gte=day_start,
    ).order_by("start_datetime")

    affected = 0

    for bt in qs:
        affected += 1

        starts_before = bt.start_datetime < day_start
        ends_after = bt.end_datetime > day_end

        # Case A: BusyTime fully inside selected day -> delete it
        if (bt.start_datetime >= day_start) and (bt.end_datetime <= day_end):
            bt.delete()
            continue

        # Case B: BusyTime covers BOTH sides -> split into two
        if starts_before and ends_after:
            # create right segment
            BusyTime.objects.create(
                user=bt.user,
                is_all_day=bt.is_all_day,
                note=bt.note,
                start_datetime=right_start,
                end_datetime=bt.end_datetime,
            )
            # keep left segment by truncating current
            bt.end_datetime = left_end
            bt.save(update_fields=["end_datetime"])
            continue

        # Case C: BusyTime ends داخل selected day -> truncate end
        if starts_before and (bt.end_datetime <= day_end):
            bt.end_datetime = left_end
            bt.save(update_fields=["end_datetime"])
            continue

        # Case D: BusyTime starts داخل selected day -> move start forward
        if (bt.start_datetime >= day_start) and ends_after:
            bt.start_datetime = right_start
            bt.save(update_fields=["start_datetime"])
            continue

    if affected:
        messages.success(request, "Busy time removed for that day.")
    else:
        messages.info(request, "No busy time found on that day.")

    # redirect back to same month
    next_qs = request.POST.get("next") or ""
    base = reverse("events:calendar")

    if next_qs.startswith("?"):
        return redirect(base + next_qs)
    if next_qs.startswith("/"):
        return redirect(next_qs)
    return redirect(base)