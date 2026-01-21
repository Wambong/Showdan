from django import forms
from .models import OfferMessage

class OfferCreateForm(forms.Form):
    proposed_amount = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class":"form-control"}))
    proposed_currency = forms.ModelChoiceField(queryset=None, widget=forms.Select(attrs={"class":"form-select"}))
    message = forms.CharField(required=False, widget=forms.Textarea(attrs={"class":"form-control", "rows":3, "placeholder":"Add a message..."}))

    def __init__(self, *args, **kwargs):
        Currency = kwargs.pop("Currency")
        super().__init__(*args, **kwargs)
        self.fields["proposed_currency"].queryset = Currency.objects.all()


class CounterOfferForm(forms.Form):
    proposed_amount = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class":"form-control"}))
    message = forms.CharField(required=False, widget=forms.Textarea(attrs={"class":"form-control", "rows":3, "placeholder":"Counter offer message..."}))


class ChatMessageForm(forms.Form):
    message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Type a message...",
        })
    )