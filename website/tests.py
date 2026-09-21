from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import AvailabilitySlot, Booking, Order, Pupil


class PackageBookingTests(TestCase):
    def setUp(self):
        self.pupil = Pupil.objects.create(name='Test pupil', phone_number='07700 900123')
        self.start = datetime(2027, 1, 10, 9, tzinfo=ZoneInfo('Europe/London'))

    def slot(self, offset=0):
        return AvailabilitySlot.objects.create(starts_at=self.start + timedelta(minutes=90 * offset))

    def test_package_prices_and_allowances(self):
        for package, count, price in [('single', 1, '59.00'), ('block', 10, '570.00'), ('intro', 3, '175.00')]:
            order = Order.objects.create(pupil=self.pupil, package=package)
            self.assertEqual((order.lesson_count, order.total_price), (count, Decimal(price)))
            self.assertEqual(order.lessons_remaining, count)
            self.assertFalse(order.bookings.exists())

    def test_phone_formats_identify_same_pupil(self):
        self.assertEqual(self.pupil.phone_number, '+447700900123')
        for phone in ['+44 7700 900123', '00447700900123', '(07700) 900-123']:
            with self.assertRaises(ValidationError):
                Pupil.objects.create(name='Duplicate', phone_number=phone)

    def test_intro_once_per_pupil_at_database_level(self):
        Order.objects.create(pupil=self.pupil, package='intro')
        with self.assertRaises(ValidationError):
            Order.objects.create(pupil=self.pupil, package='intro')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.bulk_create([Order(pupil=self.pupil, package='intro', lesson_count=3, total_price=175)])

    def test_individual_appointments_and_capacity(self):
        order = Order.objects.create(pupil=self.pupil, package='intro')
        for number in range(1, 4):
            Booking.objects.create(order=order, slot=self.slot(number), lesson_number=number)
        self.assertEqual(order.lessons_remaining, 0)
        with self.assertRaises(ValidationError):
            Booking.objects.create(order=order, slot=self.slot(4), lesson_number=4)
        with self.assertRaises(ValidationError):
            Booking.objects.create(order=order, slot=self.slot(5), lesson_number=1)

    def test_slot_cannot_be_double_booked(self):
        first = Order.objects.create(pupil=self.pupil, package='single')
        second = Order.objects.create(pupil=self.pupil, package='single')
        slot = self.slot()
        Booking.objects.create(order=first, slot=slot)
        with self.assertRaises(ValidationError):
            Booking.objects.create(order=second, slot=slot)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.bulk_create([Booking(order=second, slot=slot)])

    def test_overlaps_and_blocked_slots(self):
        self.slot()
        with self.assertRaises(ValidationError):
            AvailabilitySlot.objects.create(starts_at=self.start + timedelta(minutes=45))
        next_slot = self.slot(1)
        next_slot.is_available = False
        next_slot.save()
        order = Order.objects.create(pupil=self.pupil, package='single')
        with self.assertRaises(ValidationError):
            Booking.objects.create(order=order, slot=next_slot)

    def test_existing_order_cannot_change_package(self):
        order = Order.objects.create(pupil=self.pupil, package='intro')
        order.package = 'block'
        with self.assertRaises(ValidationError):
            order.save()

    def test_admin_pages_load(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_superuser(username='testadmin', password='test-only-password')
        self.client.force_login(user)
        for model in ['order', 'booking', 'availabilityslot', 'pupil']:
            self.assertEqual(self.client.get(f'/admin/website/{model}/').status_code, 200)
            self.assertEqual(self.client.get(f'/admin/website/{model}/add/').status_code, 200)


class BookingConfirmationTests(TestCase):
    def test_uk_time_and_confirmation_for_each_package(self):
        from django.utils import timezone
        for index, (package, price, remaining) in enumerate([
            ('single', '59.00', 0), ('block', '570.00', 9), ('intro', '175.00', 2)
        ]):
            with self.subTest(package=package):
                slot = AvailabilitySlot.objects.create(starts_at=datetime(2027, 9, 21 + index, 11, tzinfo=ZoneInfo('Europe/London')))
                slot.refresh_from_db()
                self.assertEqual(slot.starts_at.hour, 10)
                with timezone.override('Europe/London'):
                    self.assertIn('11:00 BST', str(slot))
                response = self.client.post('/booking/', {
                    'package': package, 'slot': slot.pk, 'name': 'Test Pupil',
                    'phone_number': f'0770090012{index}', 'email': ''
                })
                self.assertRedirects(response, '/booking/success/')
                page = self.client.get('/booking/success/')
                self.assertContains(page, '11:00 AM')
                self.assertContains(page, '(BST)')
                self.assertContains(page, f'£{price}')
                self.assertEqual(page.context['lessons_remaining'], remaining)
                self.assertEqual(page.context['order'].package, package)
                self.assertEqual(page.context['order'].bookings.count(), 1)
                slot.refresh_from_db()
                self.assertFalse(slot.is_available)
                self.assertContains(self.client.get('/booking/success/'), f'£{price}')

    def test_winter_slot_label(self):
        slot = AvailabilitySlot.objects.create(starts_at=datetime(2027, 1, 21, 11, tzinfo=ZoneInfo('Europe/London')))
        slot.refresh_from_db()
        self.assertIn('11:00 GMT', str(slot))

    def test_confirmation_requires_own_session(self):
        self.assertRedirects(self.client.get('/booking/success/?booking_id=1'), '/booking/')
        session = self.client.session
        session['confirmed_booking_id'] = 999999
        session.save()
        self.assertRedirects(self.client.get('/booking/success/'), '/booking/')


class AdminNextLessonTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        self.user = get_user_model().objects.create_superuser('scheduler', password='test-password')
        self.client.force_login(self.user)
        self.pupil = Pupil.objects.create(name='Sarah Jones', phone_number='07700900111')
        self.order = Order.objects.create(pupil=self.pupil, package='block')
        self.start = timezone.now() + timedelta(days=10)
        self.first_slot = AvailabilitySlot.objects.create(starts_at=self.start)
        Booking.objects.create(order=self.order, slot=self.first_slot, lesson_number=1)
        self.next_slot = AvailabilitySlot.objects.create(starts_at=self.start + timedelta(days=1))
        self.url = f'/admin/website/order/{self.order.pk}/schedule/'

    def test_link_and_only_available_future_slots(self):
        from django.utils import timezone
        blocked = AvailabilitySlot.objects.create(starts_at=self.start + timedelta(days=2), is_available=False)
        past = AvailabilitySlot.objects.create(starts_at=timezone.now() - timedelta(days=1))
        page = self.client.get(f'/admin/website/order/{self.order.pk}/change/')
        self.assertContains(page, 'Schedule next lesson')
        response = self.client.get(self.url)
        choices = response.context['form'].fields['slot'].queryset
        self.assertEqual(list(choices), [self.next_slot])
        self.assertNotIn(blocked, choices)
        self.assertNotIn(past, choices)

    def test_schedules_lesson_two_on_same_order(self):
        response = self.client.post(self.url, {'slot': self.next_slot.pk, 'lesson_number': 9})
        self.assertRedirects(response, f'/admin/website/order/{self.order.pk}/change/')
        new = Booking.objects.get(slot=self.next_slot)
        self.assertEqual(new.order, self.order)
        self.assertEqual(new.lesson_number, 2)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.order.lessons_remaining, 8)
        self.next_slot.refresh_from_db()
        self.assertFalse(self.next_slot.is_available)
        self.assertNotIn(self.next_slot, self.client.get('/booking/').context['available_slots'])

    def test_exhausted_order_cannot_schedule(self):
        for number in range(2, 11):
            slot = AvailabilitySlot.objects.create(starts_at=self.start + timedelta(days=number))
            Booking.objects.create(order=self.order, slot=slot, lesson_number=number)
        response = self.client.post(self.url, {'slot': self.next_slot.pk})
        self.assertContains(response, 'All lessons in this package are already scheduled.')
        self.assertEqual(self.order.bookings.count(), 10)
        self.next_slot.refresh_from_db()
        self.assertTrue(self.next_slot.is_available)

    def test_taken_blocked_missing_and_repeated_slots_rejected(self):
        blocked = AvailabilitySlot.objects.create(starts_at=self.start + timedelta(days=2), is_available=False)
        for slot_id in [self.first_slot.pk, blocked.pk, 999999]:
            response = self.client.post(self.url, {'slot': slot_id})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            self.assertEqual(self.order.bookings.count(), 1)
        self.client.post(self.url, {'slot': self.next_slot.pk})
        response = self.client.post(self.url, {'slot': self.next_slot.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.bookings.count(), 2)

    def test_failure_rolls_back_booking_and_slot(self):
        from unittest.mock import patch
        with patch('website.models.AvailabilitySlot.save', side_effect=ValidationError('Unable to save slot.')):
            response = self.client.post(self.url, {'slot': self.next_slot.pk})
        self.assertContains(response, 'Unable to save slot.')
        self.assertEqual(self.order.bookings.count(), 1)
        self.next_slot.refresh_from_db()
        self.assertTrue(self.next_slot.is_available)

    def test_permission_checks(self):
        from django.contrib.auth.models import Permission
        self.user.is_superuser = False
        self.user.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename='change_order'))
        self.assertEqual(self.client.post(self.url, {'slot': self.next_slot.pk}).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename='add_booking'))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_deleted_number_is_reused_without_exceeding_package(self):
        Booking.objects.filter(order=self.order).delete()
        Booking.objects.create(order=self.order, slot=self.first_slot, lesson_number=2)
        self.client.post(self.url, {'slot': self.next_slot.pk})
        self.assertEqual(Booking.objects.get(slot=self.next_slot).lesson_number, 1)


class BookingFeedbackTests(TestCase):
    def test_empty_availability_has_one_message_and_contact_link(self):
        response = self.client.get('/booking/')
        self.assertContains(response, 'No lessons are currently available.', count=1)
        self.assertContains(response, 'GET IN TOUCH →')
        self.assertNotContains(response, 'id="date-options"')
        self.assertNotContains(response, 'id="time-options"')
        self.assertNotContains(response, 'id="summary-date"')

    def test_errors_and_all_values_preserved(self):
        from django.utils import timezone
        slot = AvailabilitySlot.objects.create(starts_at=timezone.now() + timedelta(days=20))
        response = self.client.post('/booking/', {
            'package': 'block', 'slot': str(slot.pk), 'name': 'Sarah',
            'phone_number': '123', 'email': 'bad-email',
        })
        self.assertEqual(response.status_code, 200)
        for text in ['id="booking-errors"', 'id="error-name"', 'id="error-phone_number"',
                     'id="error-email"', 'value="Sarah"', 'value="123"', 'value="bad-email"',
                     'value="block" selected', 'checked']:
            self.assertContains(response, text)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(Order.objects.exists())


class PublicAccessibilityTests(TestCase):
    def test_public_markup_links_and_accessible_references(self):
        from html.parser import HTMLParser
        from urllib.parse import urlsplit
        from django.urls import resolve
        from django.contrib.staticfiles import finders
        class Audit(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []; self.refs = []; self.links = []; self.labels = []
                self.controls = []; self.h1 = 0; self.main = 0; self.description = False
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if 'id' in a: self.ids.append(a['id'])
                if tag == 'h1': self.h1 += 1
                if tag == 'main': self.main += 1
                if tag == 'meta' and a.get('name') == 'description': self.description = bool(a.get('content'))
                for key in ('aria-controls', 'aria-labelledby', 'aria-describedby'):
                    self.refs.extend(a.get(key, '').split())
                if tag == 'label': self.labels.append(a.get('for'))
                if tag in ('input', 'select', 'textarea') and a.get('type') not in ('hidden', 'radio'):
                    self.controls.append(a)
                if tag == 'img': assert 'alt' in a
                if tag == 'a':
                    self.links.append(a.get('href', ''))
                    if a.get('target') == '_blank':
                        assert {'noopener', 'noreferrer'} <= set(a.get('rel', '').split())
                        assert a.get('aria-label')
                if tag == 'script' and a.get('src', '').startswith('/static/'):
                    assert finders.find(a['src'][8:])
        for url in ('/', '/about/', '/prices/', '/booking/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                audit = Audit(); audit.feed(response.content.decode())
                self.assertEqual(audit.h1, 1); self.assertEqual(audit.main, 1)
                self.assertTrue(audit.description)
                self.assertEqual(len(audit.ids), len(set(audit.ids)))
                self.assertTrue(set(audit.refs) <= set(audit.ids))
                for control in audit.controls:
                    self.assertTrue(control.get('id') in audit.labels or control.get('aria-label'))
                for link in audit.links:
                    parsed = urlsplit(link)
                    if parsed.scheme or parsed.netloc: continue
                    if parsed.path: resolve(parsed.path)
                    elif parsed.fragment: self.assertIn(parsed.fragment, audit.ids)
        about = self.client.get('/about/').content.decode()
        self.assertEqual(about.count('VIEW RESOURCE →'), 4)


class PublicBookingSafetyTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.slot = AvailabilitySlot.objects.create(starts_at=timezone.now() + timedelta(days=30))
        self.data = {'package': 'single', 'slot': self.slot.pk, 'name': 'Sarah Jones',
                     'phone_number': '07700900555', 'email': ''}

    def test_past_slots_hidden_and_rejected(self):
        from django.utils import timezone
        past = AvailabilitySlot.objects.create(starts_at=timezone.now() - timedelta(days=1))
        self.assertNotIn(past, self.client.get('/booking/').context['available_slots'])
        response = self.client.post('/booking/', {**self.data, 'slot': past.pk})
        self.assertContains(response, 'That lesson time is no longer available.')
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Pupil.objects.exists())

    def test_intro_reuse_is_form_error_and_other_packages_still_allowed(self):
        pupil = Pupil.objects.create(name='Sarah Jones', phone_number='+447700900555')
        Order.objects.create(pupil=pupil, package='intro')
        response = self.client.post('/booking/', {**self.data, 'package': 'intro'})
        self.assertTrue(response.context['form'].errors.get('package'))
        self.assertContains(response, 'introductory offer has already been used')
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(Booking.objects.exists())
        self.slot.refresh_from_db(); self.assertTrue(self.slot.is_available)
        self.assertRedirects(self.client.post('/booking/', self.data), '/booking/success/')

    def test_blocked_booked_and_missing_slots(self):
        self.slot.is_available = False; self.slot.save()
        for slot_id in (self.slot.pk, 999999):
            response = self.client.post('/booking/', {**self.data, 'slot': slot_id})
            self.assertTrue(response.context['form'].errors.get('slot'))
        self.slot.is_available = True; self.slot.save()
        pupil = Pupil.objects.create(name='Another Pupil', phone_number='07700900666')
        order = Order.objects.create(pupil=pupil, package='single')
        Booking.objects.create(order=order, slot=self.slot)
        response = self.client.post('/booking/', self.data)
        self.assertTrue(response.context['form'].errors.get('slot'))
        self.assertEqual(Order.objects.count(), 1)

    def test_integrity_conflict_rolls_back_all_new_records(self):
        from unittest.mock import patch
        with patch('website.views.Booking.objects.create', side_effect=IntegrityError('simulated concurrent booking')):
            response = self.client.post('/booking/', self.data)
        self.assertContains(response, 'availability or package eligibility changed')
        self.assertFalse(Pupil.objects.exists()); self.assertFalse(Order.objects.exists())
        self.slot.refresh_from_db(); self.assertTrue(self.slot.is_available)

    def test_database_lock_is_friendly_but_unexpected_errors_propagate(self):
        from unittest.mock import patch
        from django.db import OperationalError
        with patch('website.views.Booking.objects.create', side_effect=OperationalError('database is locked')):
            response = self.client.post('/booking/', self.data)
        self.assertContains(response, 'Another booking is being processed')
        self.assertFalse(Order.objects.exists())
        with patch('website.views.Booking.objects.create', side_effect=OperationalError('unrelated database failure')):
            with self.assertRaises(OperationalError):
                self.client.post('/booking/', self.data)

    def test_lock_queries_do_not_join_nullable_relations(self):
        from django.db.models.query import QuerySet
        from unittest.mock import patch
        original = QuerySet._fetch_all
        locked_tables = []
        def inspect(queryset):
            if queryset.query.select_for_update:
                sql = str(queryset.query)
                self.assertNotIn('JOIN', sql)
                locked_tables.append(queryset.model)
            return original(queryset)
        with patch.object(QuerySet, '_fetch_all', inspect):
            response = self.client.post('/booking/', self.data)
        self.assertRedirects(response, '/booking/success/')
        self.assertIn(AvailabilitySlot, locked_tables)
        self.assertIn(Pupil, locked_tables)
