from django import forms
from .models import Event, EventCategory
from django.utils import timezone

class EventCategoryForm(forms.ModelForm):
    class Meta:
        model = EventCategory
        fields = ("name", "parent")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Music, Wedding, Corporate"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
        }


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = (
            "name",
            "start_datetime",
            "end_datetime",
            "country",
            "city",
            "location",
            "event_type",
            "required_professions",
            "currency",
            "event_budget",
            "advance_payment",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_datetime": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
              ),
            "end_datetime": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "event_type": forms.Select(attrs={"class": "form-select"}),
            "required_professions": forms.SelectMultiple(attrs={"class": "form-select", "size": "10"}),
            "currency": forms.Select(attrs={"class": "form-select"}),  # ✅
            "event_budget": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "advance_payment": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_datetime")
        end = cleaned.get("end_datetime")
        budget = cleaned.get("event_budget")
        advance = cleaned.get("advance_payment")

        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")

        if budget is not None and advance is not None and advance > budget:
            raise forms.ValidationError("Advance payment cannot be greater than event budget.")

        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ["start_datetime", "end_datetime"]:
            if self.instance and getattr(self.instance, f, None):
                self.initial[f] = timezone.localtime(getattr(self.instance, f)).strftime("%Y-%m-%dT%H:%M")
