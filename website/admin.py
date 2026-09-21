from django.contrib import admin
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError, OperationalError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from .admin_forms import ScheduleNextLessonForm
from .models import AvailabilitySlot, Booking, Order, Pupil


@admin.register(Pupil)
class PupilAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email')
    search_fields = ('name', 'phone_number', 'email')


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    autocomplete_fields = ('slot',)
    readonly_fields = ('created_at',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'pupil',
        'package',
        'total_price',
        'lesson_count',
        'lessons_remaining_display',
        'created_at',
    )
    list_filter = ('package',)
    search_fields = ('pupil__name', 'pupil__phone_number')
    autocomplete_fields = ('pupil',)
    readonly_fields = ('total_price', 'lesson_count', 'lessons_remaining', 'created_at', 'schedule_next_lesson')
    inlines = (BookingInline,)

    @admin.display(description='Lessons remaining')
    def lessons_remaining_display(self, obj):
        return obj.lessons_remaining

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (('pupil', 'package') if obj else ())

    @admin.display(description='Next lesson')
    def schedule_next_lesson(self, obj):
        if not obj or not obj.pk:
            return 'Save the order before scheduling a lesson.'
        if obj.lessons_remaining <= 0:
            return 'All lessons in this package are scheduled.'
        return format_html('<a href="{}">Schedule next lesson</a>', reverse(
            'admin:website_order_schedule', args=[obj.pk]))

    def get_urls(self):
        return [path('<int:order_id>/schedule/', self.admin_site.admin_view(self.schedule_view),
                     name='website_order_schedule')] + super().get_urls()

    def schedule_view(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        if not self.has_change_permission(request, order) or not request.user.has_perm('website.add_booking'):
            raise PermissionDenied
        form = ScheduleNextLessonForm(request.POST if request.method == 'POST' else None)
        if request.method == 'POST' and form.is_valid():
            try:
                with transaction.atomic():
                    order = Order.objects.select_for_update().get(pk=order_id)
                    used = set(order.bookings.values_list('lesson_number', flat=True))
                    number = next((n for n in range(1, order.lesson_count + 1) if n not in used), None)
                    if order.lessons_remaining <= 0 or number is None:
                        raise ValidationError('All lessons in this package are already scheduled.')
                    slot = AvailabilitySlot.objects.select_for_update().filter(
                        pk=form.cleaned_data['slot'].pk, is_available=True,
                        starts_at__gt=timezone.now(),
                    ).first()
                    if slot is None or Booking.objects.filter(slot_id=slot.pk).exists():
                        raise ValidationError('That time is no longer available. Please choose another.')
                    booking = Booking.objects.create(order=order, slot=slot, lesson_number=number)
                    slot.is_available = False
                    slot.save(update_fields=['is_available'])
                    self.admin_site._registry[Booking].log_addition(request, booking, 'Scheduled from existing order.')
                self.message_user(request, f'Lesson {number} scheduled for {order.pupil.name}.')
                return redirect('admin:website_order_change', order.pk)
            except ValidationError as error:
                form.add_error(None, error.messages)
            except (IntegrityError, OperationalError):
                form.add_error(None, 'Availability changed or the database is busy. Please try again.')
        return TemplateResponse(request, 'admin/website/order/schedule.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': 'Schedule next lesson', 'order': order, 'form': form,
            'has_remaining': order.lessons_remaining > 0,
        })


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ('starts_at', 'ends_at', 'is_available')
    list_filter = ('is_available', 'starts_at')
    search_fields = ('starts_at',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'pupil_name',
        'lesson_date',
        'lesson_time',
        'lesson_number',
        'package',
        'lessons_remaining',
    )
    list_filter = ('order__package', 'slot__starts_at')
    search_fields = ('order__pupil__name', 'order__pupil__phone_number', 'order__pupil__email')
    autocomplete_fields = ('order', 'slot')
    readonly_fields = ('created_at',)

    @admin.display(description='Pupil')
    def pupil_name(self, obj):
        return obj.order.pupil.name

    @admin.display(description='Date')
    def lesson_date(self, obj):
        return timezone.localtime(obj.slot.starts_at).strftime('%d %b %Y')

    @admin.display(description='Time')
    def lesson_time(self, obj):
        return timezone.localtime(obj.slot.starts_at).strftime('%H:%M')

    @admin.display(description='Package')
    def package(self, obj):
        return obj.order.get_package_display()

    @admin.display(description='Remaining')
    def lessons_remaining(self, obj):
        return obj.order.lessons_remaining
