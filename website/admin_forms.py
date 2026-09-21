from django import forms
from django.utils import timezone

from .models import AvailabilitySlot


class ScheduleNextLessonForm(forms.Form):
    slot = forms.ModelChoiceField(queryset=AvailabilitySlot.objects.none(), label='Available lesson time')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slot'].queryset = AvailabilitySlot.objects.filter(
            is_available=True, booking__isnull=True, starts_at__gt=timezone.now()
        ).order_by('starts_at')
