from datetime import timedelta
from decimal import Decimal
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


def normalize_phone_number(value):
    """Store UK local numbers and international numbers in one consistent form."""
    number = re.sub(r'[\s().-]', '', value)
    if number.startswith('00'):
        number = '+' + number[2:]
    if number.startswith('0'):
        number = '+44' + number[1:]
    elif number.startswith('44'):
        number = '+' + number
    if not re.fullmatch(r'\+[1-9][0-9]{7,14}', number):
        raise ValidationError('Enter a UK phone number or an international number with its country code.')
    return number


class Pupil(models.Model):
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)

    def clean(self):
        super().clean()
        self.phone_number = normalize_phone_number(self.phone_number)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} - {self.phone_number}'


class Order(models.Model):
    class Package(models.TextChoices):
        SINGLE = 'single', '90-minute lesson'
        BLOCK = 'block', '10 lesson block'
        INTRO = 'intro', 'New pupil introductory offer'

    PACKAGES = {
        Package.SINGLE: (1, Decimal('59.00')),
        Package.BLOCK: (10, Decimal('570.00')),
        Package.INTRO: (3, Decimal('175.00')),
    }

    pupil = models.ForeignKey(Pupil, on_delete=models.PROTECT, related_name='orders')
    package = models.CharField(max_length=20, choices=Package.choices)
    lesson_count = models.PositiveSmallIntegerField(editable=False)
    total_price = models.DecimalField(max_digits=8, decimal_places=2, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['pupil'], condition=Q(package='intro'), name='one_intro_order_per_pupil'),
            models.CheckConstraint(condition=Q(lesson_count__gte=1), name='order_has_lessons'),
            models.CheckConstraint(condition=Q(total_price__gte=0), name='order_price_nonnegative'),
        ]

    def clean(self):
        super().clean()
        if self._state.adding:
            if self.package in self.PACKAGES:
                self.lesson_count, self.total_price = self.PACKAGES[self.package]
        elif self.pk:
            original = type(self).objects.get(pk=self.pk)
            if any(getattr(self, field) != getattr(original, field)
                   for field in ('pupil_id', 'package', 'lesson_count', 'total_price')):
                raise ValidationError('An existing order’s pupil, package and price cannot be changed.')

    def save(self, *args, **kwargs):
        if self._state.adding and self.package in self.PACKAGES:
            self.lesson_count, self.total_price = self.PACKAGES[self.package]
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def lessons_remaining(self):
        return self.lesson_count - self.bookings.count()

    def __str__(self):
        return f'{self.pupil.name} — {self.get_package_display()} (order {self.pk})'


class AvailabilitySlot(models.Model):
    starts_at = models.DateTimeField(unique=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['starts_at']

    @property
    def ends_at(self):
        return self.starts_at + timedelta(minutes=90)

    def clean(self):
        super().clean()
        if not self.starts_at:
            return
        overlaps = type(self).objects.exclude(pk=self.pk).filter(
            starts_at__gt=self.starts_at - timedelta(minutes=90),
            starts_at__lt=self.ends_at,
        )
        if overlaps.exists():
            raise ValidationError({'starts_at': 'This slot overlaps another 90-minute slot.'})
        if self.pk and Booking.objects.filter(slot_id=self.pk).exists():
            original = type(self).objects.get(pk=self.pk)
            if original.starts_at != self.starts_at:
                raise ValidationError({'starts_at': 'A booked slot cannot be moved. Reassign the booking instead.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        local_start = timezone.localtime(self.starts_at)
        return f'{local_start:%d %b %Y %H:%M %Z} (90 minutes)'


class Booking(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='bookings')
    slot = models.OneToOneField(AvailabilitySlot, on_delete=models.PROTECT, related_name='booking')
    lesson_number = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'lesson_number'], name='unique_lesson_in_order'),
            models.CheckConstraint(condition=Q(lesson_number__gte=1), name='positive_lesson_number'),
        ]

    def clean(self):
        super().clean()
        if self.order_id and self.lesson_number is not None:
            if not 1 <= self.lesson_number <= self.order.lesson_count:
                raise ValidationError({'lesson_number': f'Choose a lesson number from 1 to {self.order.lesson_count}.'})
        if self.slot_id and not self.slot.is_available:
            existing_slot = type(self).objects.filter(pk=self.pk, slot_id=self.slot_id).exists()
            if not existing_slot:
                raise ValidationError({'slot': 'This slot is not available for booking.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.order.pupil.name} — lesson {self.lesson_number} — {self.slot}'
