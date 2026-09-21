from django import forms

from .models import Order, normalize_phone_number


class NewBookingForm(forms.Form):
    package = forms.ChoiceField(
        choices=Order.Package.choices
    )

    name = forms.CharField(
        max_length=100
    )

    phone_number = forms.CharField(
        max_length=20
    )

    email = forms.EmailField(
        required=False
    )

    slot = forms.IntegerField()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name.split()) < 2:
            raise forms.ValidationError("Please enter your first name and surname.")
        return name

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"]
        return normalize_phone_number(phone_number)
