from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db.models import Q
class AccountsManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class Profession(models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
    )

    # NEW: sortable tree path
    path = models.CharField(max_length=600, blank=True, db_index=True)

    class Meta:
        unique_together = ("name", "parent")
        ordering = ["path"]  # ✅ tree order, not global name

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
        # build hierarchical path like: "000001.music/000002.live/000003.acapella"
        super().save(*args, **kwargs)  # ensure self.pk exists

        if self.parent_id:
            parent_path = Profession.objects.filter(pk=self.parent_id).values_list("path", flat=True).first() or ""
            new_path = f"{parent_path}/{self.pk:06d}.{self.name.lower()}"
        else:
            new_path = f"{self.pk:06d}.{self.name.lower()}"

        # update only if changed (avoid infinite recursion)
        if self.path != new_path:
            Profession.objects.filter(pk=self.pk).update(path=new_path)

            # IMPORTANT: if name or parent changes, children paths must update too
            for child in self.children.all():
                child.save()





class Review(models.Model):
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_given",
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["professional", "reviewer"],
                name="unique_review_per_reviewer_per_professional",
            )
        ]

    def __str__(self):
        return f"{self.reviewer} → {self.professional} ({self.rating})"


class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Currency(models.Model):
    name = models.CharField(max_length=80, unique=True)   # e.g. US Dollar
    sign = models.CharField(max_length=8)                 # e.g. $

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.sign})"

class Accounts(AbstractBaseUser, PermissionsMixin):
    class AccountType(models.TextChoices):
        PERSONAL = "personal", "Personal"
        PROFESSIONAL = "professional", "Professional"
    # Auth identity
    class Gender(models.TextChoices):
        PERSONAL = "male", "Male"
        PROFESSIONAL = "female", "Female"
    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        default="avatars/default.png",
    )
    professional_picture = models.ImageField(
        upload_to="professional_pictures/",
        blank=True,
        null=True,
        default="professional_pictures/default_professional.png",
    )
    communication_languages = models.ManyToManyField(
        "accounts.Language",
        blank=True,
        related_name="accounts_communication",
    )

    event_languages = models.ManyToManyField(
        "accounts.Language",
        blank=True,
        related_name="accounts_events",
    )
    accepted_event_categories = models.ManyToManyField(
        "events.EventCategory",
        blank=True,
        related_name="accepted_by_users",
    )
    # Basic person info
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    nickname = models.CharField(max_length=220, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    years_of_experience = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
    )
    about_me = models.TextField(blank=True, default="")

    # Account type
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.PERSONAL,
    )
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True, null=True)
    # Professional link (can be empty for personal accounts)
    professions = models.ManyToManyField(
        Profession,
        blank=True,
        related_name="accounts",
    )
    currency = models.ForeignKey(
        "accounts.Currency",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accounts",
    )

    cost_per_hour = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    cost_per_5_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # Django required-ish fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    country = models.CharField(max_length=120, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")

    objects = AccountsManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.email} ({self.account_type})"

    def clean(self):
        """
        Optional: you can enforce professional accounts must have professions.
        Note: M2M isn't available until after save; enforce this via forms/serializer too.
        """
        super().clean()


class AccountPhoto(models.Model):
    """✅ multiple normal pictures per user"""
    user = models.ForeignKey(
        "accounts.Accounts",
        on_delete=models.CASCADE,
        related_name="normal_photos",
    )
    image = models.ImageField(upload_to="normal_pictures/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.user.email} photo ({self.id})"

class ProfessionalPhoto(models.Model):
    user = models.ForeignKey(
        "accounts.Accounts",
        on_delete=models.CASCADE,
        related_name="professional_photos",
    )
    image = models.ImageField(upload_to="professional_pictures/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.user.email} professional photo"


class AudioAcapellaCover(models.Model):
    user = models.ForeignKey(
        "accounts.Accounts",
        on_delete=models.CASCADE,
        related_name="audio_acapella_covers",
    )
    title = models.CharField(max_length=150, blank=True)
    audio_file = models.FileField(upload_to="acapella/audio/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or f"Audio cover #{self.id}"


class VideoAcapellaCover(models.Model):
    user = models.ForeignKey(
        "accounts.Accounts",
        on_delete=models.CASCADE,
        related_name="video_acapella_covers",
    )
    title = models.CharField(max_length=150, blank=True)
    video_file = models.FileField(upload_to="acapella/video/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or f"Video cover #{self.id}"



class ExchangeRate(models.Model):
    """
    Stores conversion rate from one currency to another.
    Example: USD -> NGN rate=1500.00 means 1 USD = 1500 NGN.
    """
    from_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="rates_from")
    to_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="rates_to")
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("from_currency", "to_currency")

    def __str__(self):
        return f"1 {self.from_currency.sign} -> {self.rate} {self.to_currency.sign}"


