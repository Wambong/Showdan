from django import forms
from .models import Profession, Language, Currency, ExchangeRate, NewsPost
from django.contrib.auth import get_user_model

from events.models import EventCategory
User = get_user_model()

class AdminUserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "profile_picture",
            "professional_picture",
            "first_name",
            "last_name",
            "nickname",
            "email",
            "phone",
            "gender",
            "account_type",
            "is_active",
            "is_staff",
            "currency",
            "cost_per_hour",
            "cost_per_5_hours",
        )
        widgets = {
            "account_type": forms.Select(attrs={"class": "form-select"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "nickname": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "cost_per_hour": forms.NumberInput(attrs={"class": "form-control"}),
            "cost_per_5_hours": forms.NumberInput(attrs={"class": "form-control"}),
        }
class ProfessionForm(forms.ModelForm):
    class Meta:
        model = Profession
        fields = ("name", "parent")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
        }

class EventCategoryForm(forms.ModelForm):
    class Meta:
        model = EventCategory
        fields = ("name", "parent")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
        }

class LanguageForm(forms.ModelForm):
    class Meta:
        model = Language
        fields = ("name", "slug")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
        }

class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = ("name", "sign")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "sign": forms.TextInput(attrs={"class": "form-control"}),
        }

class ExchangeRateForm(forms.ModelForm):
    class Meta:
        model = ExchangeRate
        fields = ("from_currency", "to_currency", "rate")
        widgets = {
            "from_currency": forms.Select(attrs={"class": "form-select"}),
            "to_currency": forms.Select(attrs={"class": "form-select"}),
            "rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001"}),
        }


class NewsPostForm(forms.ModelForm):
    class Meta:
        model = NewsPost
        fields = ["title", "excerpt", "body", "image", "is_published"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "excerpt": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }