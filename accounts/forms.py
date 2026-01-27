from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import Profession, Review
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
User = get_user_model()
from django.utils.translation import gettext_lazy as _
import re
class AccountsRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "phone",
            "country",
            "city",
            "date_of_birth",
            "account_type",
        )

class AccountsProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "nickname",
            "phone",
            "country",
            "city",
            "address",
            "gender",
            "date_of_birth",
            "profile_picture",
            "professional_picture",
            "account_type",
            "professions",
            "years_of_experience",
            "about_me",
            "communication_languages",
            "event_languages",
            "accepted_event_categories",

            "currency",
            "cost_per_hour",
            "cost_per_5_hours",

        )
        widgets = {
            "about_me": forms.Textarea(attrs={
                "rows": 6,
                "placeholder": _("Tell people about yourself..."),
            }),
            "communication_languages": forms.SelectMultiple(attrs={"class": "form-select", "size": "6"}),
            "event_languages": forms.SelectMultiple(attrs={"class": "form-select", "size": "6"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "cost_per_hour": forms.NumberInput(attrs={"class": "form-control"}),
            "cost_per_5_hours": forms.NumberInput(attrs={"class": "form-control"}),
            "accepted_event_categories": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
        }
    def clean_about_me(self):
        text = (self.cleaned_data.get("about_me") or "").strip()
        # count words: sequences of non-whitespace
        words = re.findall(r"\S+", text)
        if len(words) > 1000:
            raise forms.ValidationError("About me must be 1000 words or less.")
        return text

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If personal, hide professions on the edit form UI
        if self.instance and self.instance.account_type == User.AccountType.PERSONAL:
            self.fields["professions"].required = False

    def clean(self):
        cleaned = super().clean()

        # pricing validation
        currency = cleaned.get("currency")
        hour = cleaned.get("cost_per_hour")
        five = cleaned.get("cost_per_5_hours")
        if (hour is not None or five is not None) and not currency:
            raise forms.ValidationError("Please select a currency before entering costs.")

        # professions validation
        account_type = cleaned.get("account_type")
        professions = cleaned.get("professions")
        if account_type == User.AccountType.PROFESSIONAL and not professions:
            raise forms.ValidationError("Professional accounts must select at least one profession.")

        return cleaned

    def clean_years_of_experience(self):
        val = self.cleaned_data.get("years_of_experience")
        if val is None:
            return val
        if val > 60:
            raise forms.ValidationError("Years of experience must be 60 or less.")
        return val


class ProfessionForm(forms.ModelForm):
    class Meta:
        model = Profession
        fields = ("name", "parent")

class DashCurrencyForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("currency",)
        widgets = {
            "currency": forms.Select(attrs={"class": "form-select"}),
        }

class DashLanguageForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("communication_languages", "event_languages")
        widgets = {
            "communication_languages": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "event_languages": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
        }

class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """
    Accepts multiple uploaded files and returns a list of files.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultiFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # If no file chosen, accept empty (when required=False)
        if not data:
            return []
        # When multiple, data is a list/tuple
        if isinstance(data, (list, tuple)):
            files = []
            for f in data:
                files.append(super().clean(f, initial))
            return files
        # Fallback single
        return [super().clean(data, initial)]


class NormalPhotosUploadForm(forms.Form):
    normal_images = MultipleFileField(required=False)


class ProfessionalPhotosUploadForm(forms.Form):
    professional_images = MultipleFileField(required=False)

class AudioCoversUploadForm(forms.Form):
    audio_files = MultipleFileField(required=False)

class VideoCoversUploadForm(forms.Form):
    video_files = MultipleFileField(required=False)



class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i} stars") for i in range(5, 0, -1)],
        coerce=int,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {
            "comment": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder":_("Write your review (optional)...")
            }),
        }



