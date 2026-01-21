from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.urls import reverse
from accounts.models import Currency
from accounts.utils import get_rate
from django.db.models import Max, Q
from .models import Event, OfferThread, OfferMessage
from .forms_offers import OfferCreateForm, CounterOfferForm, ChatMessageForm
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings
from datetime import datetime, time
from django.utils import timezone
from django.contrib.auth import get_user_model
User = get_user_model()
def safe_next_url(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback


def is_professional(user):
    return getattr(user, "account_type", None) == "professional"


@login_required
def offer_thread_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # who can open?
    # - event creator
    # - professional with an existing thread
    if request.user != event.created_by and not is_professional(request.user):
        messages.error(request, "You are not allowed to view offers for this event.")
        return redirect("events:list")

    # If professional: open their own thread
    if is_professional(request.user) and request.user != event.created_by:

        # If locked, do NOT create a new thread
        if event.is_locked:
            thread = OfferThread.objects.filter(event=event, professional=request.user).first()
            if not thread:
                messages.error(request, "This event is locked. You cannot create a new offer thread.")
                return redirect("events:list")
        else:
            thread, _ = OfferThread.objects.get_or_create(event=event, professional=request.user)

    else:
        # creator must specify which professional thread via ?pro=<id>
        pro_id = request.GET.get("pro")
        if not pro_id:
            messages.error(request, "Select a professional offer thread to view.")
            return redirect("events:list")
        thread = get_object_or_404(OfferThread, event=event, professional_id=pro_id)

    messages_qs = thread.messages.select_related("sender", "proposed_currency", "event_currency")

    offer_form = None
    counter_form = None

    if is_professional(request.user) and request.user == thread.professional:
        offer_form = OfferCreateForm(Currency=Currency)
    if request.user == event.created_by:
        counter_form = CounterOfferForm()

    return render(request, "events/offer_thread.html", {
        "event": event,
        "thread": thread,
        "msgs": messages_qs,
        "offer_form": offer_form,
        "counter_form": counter_form,
        "is_creator": request.user == event.created_by,
        "is_pro": request.user == thread.professional,
    })


@login_required
@transaction.atomic
def send_offer_message(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if event.is_locked:
        messages.error(request, "This event is locked. New offers/counter-offers are disabled.")
        return redirect("events:list")

    if not is_professional(request.user):
        messages.error(request, "Only professional accounts can make booking offers.")
        return redirect("events:list")

    if request.method != "POST":
        return redirect("events:offer_thread", event_id=event.id)

    # event might have been locked in another request
    event.refresh_from_db(fields=["is_locked"])
    if event.is_locked:
        messages.error(request, "This event is locked because an offer has already been accepted.")
        return redirect("events:list")

    thread, _ = OfferThread.objects.get_or_create(event=event, professional=request.user)

    form = OfferCreateForm(request.POST, Currency=Currency)
    if not form.is_valid():
        messages.error(request, "Please correct the errors in your offer.")
        return redirect("events:offer_thread", event_id=event.id)

    amount = form.cleaned_data["proposed_amount"]
    from_cur = form.cleaned_data["proposed_currency"]
    msg = form.cleaned_data.get("message") or ""

    # convert to event currency if possible
    event_cur = event.currency
    rate = None
    converted = None
    if event_cur and from_cur:
        rate = get_rate(from_cur, event_cur)
        if rate:
            converted = (amount * rate).quantize(amount)  # same decimals as amount
        else:
            messages.warning(request, "No exchange rate found for conversion. Offer saved without conversion.")

    OfferMessage.objects.create(
        thread=thread,
        sender=request.user,
        sender_type=OfferMessage.SenderType.PROFESSIONAL,
        message=msg,
        proposed_amount=amount,
        proposed_currency=from_cur,
        event_currency=event_cur,
        conversion_rate=rate,
        converted_amount=converted,
        status=OfferMessage.Status.PENDING,
    )

    messages.success(request, "Offer sent.")
    return redirect(safe_next_url(request, f"/events/my-offers/?thread={thread.id}"))



@login_required
@transaction.atomic
def counter_offer_view(request, event_id, pro_id):
    event = get_object_or_404(Event, id=event_id, created_by=request.user)
    thread = get_object_or_404(OfferThread, event=event, professional_id=pro_id)

    if event.is_locked:
        messages.error(request, "This event is locked. New offers/counter-offers are disabled.")
        return redirect(f"/events/my-offers/?thread={thread.id}")

    if request.method != "POST":
        return redirect("events:offer_thread", event_id=event.id)

    form = CounterOfferForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the counter-offer.")
        return redirect(f"{redirect('events:offer_thread', event_id=event.id).url}?pro={pro_id}")

    amount = form.cleaned_data["proposed_amount"]
    msg = form.cleaned_data.get("message") or ""

    # creator counter-offer uses event currency (recommended)
    event_cur = event.currency
    OfferMessage.objects.create(
        thread=thread,
        sender=request.user,
        sender_type=OfferMessage.SenderType.CREATOR,
        message=msg,
        proposed_amount=amount,
        proposed_currency=event_cur,
        event_currency=event_cur,
        conversion_rate=1 if event_cur else None,
        converted_amount=amount if event_cur else None,
        status=OfferMessage.Status.PENDING,
    )

    messages.success(request, "Counter-offer sent.")
    return redirect(safe_next_url(request, f"/events/my-offers/?thread={thread.id}"))

@login_required
@transaction.atomic
def accept_offer_view(request, event_id, pro_id):
    event = get_object_or_404(Event, id=event_id, created_by=request.user)
    thread = get_object_or_404(OfferThread, event=event, professional_id=pro_id)

    # Accept the latest proposal message in this thread
    last = (
        thread.messages
        .filter(proposed_amount__isnull=False)
        .order_by("-created_at")
        .first()
    )
    if not last:
        messages.error(request, "No offer to accept.")
        return redirect(f"{reverse('events:offer_thread', args=[event.id])}?pro={pro_id}")

    # Lock event + record accepted thread
    event.is_locked = True
    event.accepted_thread = thread
    event.save(update_fields=["is_locked", "accepted_thread"])

    # Mark this message accepted
    last.status = OfferMessage.Status.ACCEPTED
    last.save(update_fields=["status"])

    messages.success(request, "Offer accepted.")
    return redirect(safe_next_url(request, f"/events/my-offers/?thread={thread.id}"))

@login_required
@transaction.atomic
def reject_offer_view(request, event_id, pro_id):
    event = get_object_or_404(Event, id=event_id, created_by=request.user)
    thread = get_object_or_404(OfferThread, event=event, professional_id=pro_id)

    last = thread.messages.filter(proposed_amount__isnull=False).order_by("-created_at").first()
    if not last:
        messages.error(request, "No offer to reject.")
        return redirect(f"{redirect('events:offer_thread', event_id=event.id).url}?pro={pro_id}")

    last.status = OfferMessage.Status.REJECTED
    last.save(update_fields=["status"])

    messages.success(request, "Offer rejected.")
    return redirect(safe_next_url(request, f"/events/my-offers/?thread={thread.id}"))



@login_required
def offers_inbox_view(request):
    user = request.user

    # threads where:
    # - user is the professional (offers you sent)
    # - OR user is the creator of the event (offers sent to your events)
    threads = (
        OfferThread.objects
        .select_related("event", "event__created_by", "event__currency", "professional")
        .filter(Q(professional=user) | Q(event__created_by=user))
        .annotate(last_msg_at=Max("messages__created_at"))
        .order_by("-last_msg_at", "-created_at")
    )

    # Optional: allow opening by event id for professionals (creates thread if needed)
    event_id = request.GET.get("event")
    if event_id and user.account_type == "professional":
        event = get_object_or_404(Event, id=event_id)
        if event.created_by_id == user.id:
            messages.error(request, "You cannot make an offer on your own event.")
            return redirect("events:offers_inbox")

        if event.is_locked:
            messages.error(request, "This event is locked. You cannot create a new offer thread.")
            return redirect("events:offers_inbox")

        thread, _ = OfferThread.objects.get_or_create(event=event, professional=user)
        return redirect(f"{request.path}?thread={thread.id}")


    # Select thread from query string
    thread_id = request.GET.get("thread")
    active_thread = None

    if thread_id:
        active_thread = get_object_or_404(
            OfferThread.objects.select_related("event", "event__created_by", "event__currency", "professional"),
            id=thread_id,
        )
        # Permission check
        if active_thread.professional_id != user.id and active_thread.event.created_by_id != user.id:
            messages.error(request, "You are not allowed to view this thread.")
            return redirect("events:offers_inbox")

    # Default to first thread if none selected
    if not active_thread and threads.exists():
        active_thread = threads.first()

    msgs = []
    if active_thread:
        msgs = (
            active_thread.messages
            .select_related("sender", "proposed_currency", "event_currency")
            .all()
        )

    # Forms
    offer_form = None
    counter_form = None

    is_pro = active_thread and (active_thread.professional_id == user.id)
    is_creator = active_thread and (active_thread.event.created_by_id == user.id)

    if is_pro:
        offer_form = OfferCreateForm(Currency=Currency)

    if is_creator:
        counter_form = CounterOfferForm()

    return render(request, "events/offers_inbox.html", {
        "threads": threads,
        "active_thread": active_thread,
        "msgs": msgs,
        "offer_form": offer_form,
        "counter_form": counter_form,
        "is_pro": is_pro,
        "is_creator": is_creator,
    })





@login_required
@transaction.atomic
def send_chat_message_view(request, thread_id):
    thread = get_object_or_404(
        OfferThread.objects.select_related("event", "event__created_by"),
        id=thread_id
    )
    event = thread.event
    user = request.user

    # must be participant
    if user.id != thread.professional_id and user.id != event.created_by_id:
        messages.error(request, "You are not allowed in this thread.")
        return redirect("events:offers_inbox")

    # if locked: only accepted thread can send messages
    if event.is_locked and event.accepted_thread_id != thread.id:
        messages.error(request, "This event is locked. Only the accepted offer thread can continue chatting.")
        return redirect(f"/events/my-offers/?thread={thread.id}")

    if request.method != "POST":
        return redirect(f"/events/my-offers/?thread={thread.id}")

    text = (request.POST.get("message") or "").strip()
    if not text:
        messages.error(request, "Please type a message.")
        return redirect(f"/events/my-offers/?thread={thread.id}")

    OfferMessage.objects.create(
        thread=thread,
        sender=user,
        sender_type=OfferMessage.SenderType.PROFESSIONAL if is_professional(user) else OfferMessage.SenderType.CREATOR,
        message=text,
    )
    return redirect(f"/events/my-offers/?thread={thread.id}")



@login_required
def booking_request_from_calendar_view(request, pro_id):
    """
    Create a lightweight Event for the selected date/time and open a thread with that professional.
    """
    prof = get_object_or_404(User, id=pro_id, account_type="professional", is_active=True)

    day_str = request.GET.get("date")
    start_str = request.GET.get("start")  # "HH:MM"
    end_str = request.GET.get("end")      # "HH:MM"

    if not day_str:
        messages.error(request, "Please select a date.")
        return redirect("accounts:public_profile_detail", pk=prof.id)

    if not start_str or not end_str:
        messages.error(request, "Please select a start time and end time.")
        return redirect(f"{redirect('accounts:public_profile_detail', pk=prof.id).url}?tab=calendar")

    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Invalid date.")
        return redirect(f"{redirect('accounts:public_profile_detail', pk=prof.id).url}?tab=calendar")

    try:
        sh, sm = [int(x) for x in start_str.split(":")]
        eh, em = [int(x) for x in end_str.split(":")]
        start_t = time(sh, sm)
        end_t = time(eh, em)
    except Exception:
        messages.error(request, "Invalid time selection.")
        return redirect(f"{redirect('accounts:public_profile_detail', pk=prof.id).url}?tab=calendar")

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(day, start_t), tz)
    end_dt = timezone.make_aware(datetime.combine(day, end_t), tz)

    if end_dt <= start_dt:
        messages.error(request, "End time must be after start time.")
        return redirect(f"{redirect('accounts:public_profile_detail', pk=prof.id).url}?tab=calendar")

    # block past dates (optional but recommended)
    if day < timezone.localdate():
        messages.error(request, "You cannot create a booking request in the past.")
        return redirect(f"{redirect('accounts:public_profile_detail', pk=prof.id).url}?tab=calendar")

    # Create an Event owned by the requester (current user)
    e = Event.objects.create(
        name=f"Booking request with {prof.first_name} {prof.last_name}",
        start_datetime=start_dt,
        end_datetime=end_dt,
        location="",
        created_by=request.user,
        currency=(request.user.currency if getattr(request.user, "currency", None) else None),
        is_locked=False,
        is_posted=False,
    )

    # Create thread
    thread, _ = OfferThread.objects.get_or_create(event=e, professional=prof)

    return redirect(f"/events/my-offers/?thread={thread.id}")


