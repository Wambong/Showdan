from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
class EventCategory(models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
    )

    path = models.CharField(max_length=600, blank=True, db_index=True)

    class Meta:
        verbose_name_plural = "Event categories"
        unique_together = ("name", "parent")
        ordering = ["path"]

    def get_depth(self):
        depth = 0
        p = self.parent
        while p:
            depth += 1
            p = p.parent
        return depth

    def __str__(self):
        indent = "— " * self.get_depth()
        return f"{indent}{self.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.parent_id:
            parent_path = EventCategory.objects.filter(pk=self.parent_id).values_list("path", flat=True).first() or ""
            new_path = f"{parent_path}/{self.pk:06d}.{self.name.lower()}"
        else:
            new_path = f"{self.pk:06d}.{self.name.lower()}"

        if self.path != new_path:
            EventCategory.objects.filter(pk=self.pk).update(path=new_path)
            for child in self.children.all():
                child.save()



class Event(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=120, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    event_type = models.ForeignKey(
        "events.EventCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )

    required_professions = models.ManyToManyField(
        "accounts.Profession",
        blank=True,
        related_name="events",
    )

    # ✅ Datetimes
    start_datetime = models.DateTimeField(default=timezone.now)
    end_datetime = models.DateTimeField()
    currency = models.ForeignKey(
        "accounts.Currency",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    # ✅ Budget
    event_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    advance_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    # ✅ lock event once an offer is accepted
    is_locked = models.BooleanField(default=False)
    is_posted = models.BooleanField(default=True)

    # (optional but useful) remember who won
    accepted_thread = models.ForeignKey(
        "events.OfferThread",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_for_events",
    )
    # ✅ NEW
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events_created",
    )
    accepted_professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.created_by:
            if not self.country:
                self.country = getattr(self.created_by, "country", "") or ""
            if not self.city:
                self.city = getattr(self.created_by, "city", "") or ""
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        if self.end_datetime and self.start_datetime and self.end_datetime <= self.start_datetime:
            from django.core.exceptions import ValidationError
            raise ValidationError({"end_datetime": "End time must be after start time."})

        if (
            self.event_budget is not None
            and self.advance_payment is not None
            and self.advance_payment > self.event_budget
        ):
            from django.core.exceptions import ValidationError
            raise ValidationError({"advance_payment": "Advance payment cannot be greater than event budget."})

    def __str__(self):
        return self.name


class OfferThread(models.Model):
    """
    One private conversation thread per (event, professional).
    """
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="offer_threads")
    professional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offer_threads")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "professional")

    def __str__(self):
        return f"Thread: {self.event_id} / {self.professional_id}"


class OfferMessage(models.Model):
    class SenderType(models.TextChoices):
        PROFESSIONAL = "professional", "Professional"
        CREATOR = "creator", "Creator"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    thread = models.ForeignKey("events.OfferThread", on_delete=models.CASCADE, related_name="messages")

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offer_messages")
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)

    message = models.TextField(blank=True)

    # optional "proposal terms" for this message (offer or counter-offer)
    proposed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    proposed_currency = models.ForeignKey(
        "accounts.Currency",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="offer_messages_currency",
    )

    # store conversion snapshot at time of proposal
    event_currency = models.ForeignKey(
        "accounts.Currency",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="offer_messages_event_currency",
    )
    conversion_rate = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    converted_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # status changes only apply when creator decides
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.thread_id} - {self.sender_type} - {self.status}"


class BusyTime(models.Model):
    """
    User marks time they are unavailable to work.
    Supports single day or multi-day ranges, all-day or timed.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="busy_times")

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    is_all_day = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_datetime"]

    def __str__(self):
        return f"{self.user_id} busy {self.start_datetime} -> {self.end_datetime}"