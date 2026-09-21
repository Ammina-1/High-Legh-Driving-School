from django.shortcuts import render, redirect
from django.db import transaction, IntegrityError, OperationalError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .forms import NewBookingForm
from .models import (
    Pupil,
    Order,
    Booking,
    AvailabilitySlot,
)


def home(request):
    return render(request, "website/index.html")


def about(request):
    return render(request, "website/about.html")


def prices(request):
    return render(request, "website/prices.html")


def booking(request):
    form = NewBookingForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                # Lock only the slot table, then check the related booking separately.
                slot = AvailabilitySlot.objects.select_for_update().filter(
                    pk=form.cleaned_data["slot"],
                ).first()
                if (slot is None or not slot.is_available or slot.starts_at <= timezone.now()
                        or Booking.objects.filter(slot_id=slot.pk).exists()):
                    raise ValidationError({"slot": "That lesson time is no longer available. Please choose another."})

                pupil, created = Pupil.objects.get_or_create(
                    phone_number=form.cleaned_data["phone_number"],
                    defaults={"name": form.cleaned_data["name"], "email": form.cleaned_data["email"]},
                )
                # Serialise package eligibility checks for an existing pupil.
                pupil = Pupil.objects.select_for_update().get(pk=pupil.pk)
                if (form.cleaned_data["package"] == Order.Package.INTRO
                        and pupil.orders.filter(package=Order.Package.INTRO).exists()):
                    raise ValidationError({"package": "The introductory offer has already been used for this phone number. Please choose another package."})

                order = Order.objects.create(pupil=pupil, package=form.cleaned_data["package"])
                first_booking = Booking.objects.create(order=order, slot=slot, lesson_number=1)
                slot.is_available = False
                slot.save(update_fields=["is_available"])
        except ValidationError as error:
            if hasattr(error, "error_dict"):
                for field, errors in error.error_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                form.add_error(None, error)
        except IntegrityError:
            # The transaction has rolled back before rendering errors or querying again.
            form.add_error(None, "Your booking could not be completed because availability or package eligibility changed. Please check your selections and try again.")
        except OperationalError as error:
            cause = error.__cause__
            code = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
            if code not in {"40001", "40P01", "55P03"} and "locked" not in str(error).lower():
                raise
            form.add_error(None, "Another booking is being processed. Please try again in a moment.")
        else:
            request.session["confirmed_booking_id"] = first_booking.pk
            return redirect("booking_success")

    # Refresh availability after any failed transaction, including stale submissions.
    available_slots = AvailabilitySlot.objects.filter(
        is_available=True, booking__isnull=True, starts_at__gt=timezone.now(),
    ).order_by("starts_at")

    return render(
        request,
        "website/booking.html",
        {
            "form": form,
            "available_slots": available_slots,
        },
    )


@never_cache
def booking_success(request):
    booking_id = request.session.get("confirmed_booking_id")
    confirmed_booking = Booking.objects.select_related("order", "slot").filter(pk=booking_id).first()
    if confirmed_booking is None:
        return redirect("booking")
    return render(request, "website/booking_success.html", {
        "confirmed_booking": confirmed_booking,
        "order": confirmed_booking.order,
        "lessons_remaining": confirmed_booking.order.lessons_remaining,
    })
