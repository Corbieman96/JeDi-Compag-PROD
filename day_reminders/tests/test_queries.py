from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from day_reminders.models import DayReminder, DayReminderCompletion, DayReminderException
from day_reminders.services import actions
from day_reminders.services.queries import reminders_for_date


class RemindersForDateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u1", password="x")

    def test_one_off_visible_only_on_pinned_day(self):
        d = date(2026, 4, 27)
        DayReminder.objects.create(
            title="Jedna",
            text="A",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=d,
            created_by=self.user,
        )
        self.assertEqual(len(reminders_for_date(d)), 1)
        self.assertEqual(len(reminders_for_date(date(2026, 4, 28))), 0)

    def test_rolling_carries_until_completed(self):
        d0 = date(2026, 4, 1)
        d1 = date(2026, 4, 26)
        r = DayReminder.objects.create(
            title="Rolující",
            text="R",
            kind=DayReminder.Kind.ROLLING,
            rolling_start=d0,
            created_by=self.user,
        )
        self.assertIn(r, reminders_for_date(d1))
        r.completed_at = timezone.now()
        r.save()
        self.assertNotIn(r, reminders_for_date(d1))

    def test_weekly_reschedule(self):
        thu = date(2026, 4, 30)
        r = DayReminder.objects.create(
            title="Týden",
            text="W",
            kind=DayReminder.Kind.WEEKLY,
            repeat_weekdays=[1],  # úterý
            repeat_active_from=date(2026, 4, 1),
            created_by=self.user,
        )
        tue = date(2026, 4, 28)
        self.assertIn(r, reminders_for_date(tue))
        DayReminderException.objects.create(reminder=r, original_date=tue, rescheduled_to=thu)
        self.assertNotIn(r, reminders_for_date(tue))
        self.assertIn(r, reminders_for_date(thu))

    def test_weekly_multiple_weekdays(self):
        r = DayReminder.objects.create(
            title="Víc dnů",
            text="Multi",
            kind=DayReminder.Kind.WEEKLY,
            repeat_weekdays=[0, 2, 4],
            repeat_active_from=date(2026, 4, 1),
            created_by=self.user,
        )
        mon = date(2026, 4, 27)
        wed = date(2026, 4, 29)
        fri = date(2026, 5, 1)
        tue = date(2026, 4, 28)
        self.assertIn(r, reminders_for_date(mon))
        self.assertIn(r, reminders_for_date(wed))
        self.assertIn(r, reminders_for_date(fri))
        self.assertNotIn(r, reminders_for_date(tue))

    def test_rolling_hidden_after_toggle_complete_on_next_day(self):
        d0 = date(2026, 6, 10)
        d_resolve = date(2026, 6, 16)
        d_next = date(2026, 6, 17)
        r = DayReminder.objects.create(
            title="Vrátit 3x stůl",
            text="dílna",
            kind=DayReminder.Kind.ROLLING,
            rolling_start=d0,
            created_by=self.user,
        )
        self.assertIn(r, reminders_for_date(d_resolve))
        actions.toggle_reminder_completion_for_day(r.pk, d_resolve, self.user)
        self.assertNotIn(r, reminders_for_date(d_next))

    def test_rolling_reappears_after_uncomplete(self):
        d0 = date(2026, 6, 10)
        d_resolve = date(2026, 6, 16)
        d_next = date(2026, 6, 17)
        r = DayReminder.objects.create(
            title="Rolující",
            text="R",
            kind=DayReminder.Kind.ROLLING,
            rolling_start=d0,
            created_by=self.user,
        )
        actions.toggle_reminder_completion_for_day(r.pk, d_resolve, self.user)
        self.assertNotIn(r, reminders_for_date(d_next))
        actions.toggle_reminder_completion_for_day(r.pk, d_resolve, self.user)
        self.assertIn(r, reminders_for_date(d_next))

    def test_rolling_hidden_after_legacy_completion_without_completed_at(self):
        d0 = date(2026, 6, 10)
        d_resolve = date(2026, 6, 16)
        d_next = date(2026, 6, 17)
        r = DayReminder.objects.create(
            title="Legacy rolling",
            text="",
            kind=DayReminder.Kind.ROLLING,
            rolling_start=d0,
            created_by=self.user,
        )
        DayReminderCompletion.objects.create(
            reminder=r,
            resolved_on=d_resolve,
            resolved_by=self.user,
        )
        self.assertIn(r, reminders_for_date(d_resolve))
        self.assertNotIn(r, reminders_for_date(d_next))

    def test_snooze_hides_until_date(self):
        r = DayReminder.objects.create(
            title="Snooze",
            text="S",
            kind=DayReminder.Kind.ROLLING,
            rolling_start=date(2026, 5, 1),
            snoozed_until=date(2026, 5, 15),
            created_by=self.user,
        )
        self.assertNotIn(r, reminders_for_date(date(2026, 5, 12)))
        self.assertIn(r, reminders_for_date(date(2026, 5, 15)))

    def test_monthly_first_wednesday(self):
        r = DayReminder.objects.create(
            title="Měsíční",
            text="M",
            kind=DayReminder.Kind.MONTHLY,
            repeat_monthly={"ordinal": 1, "weekday": 2},
            repeat_active_from=date(2026, 1, 1),
            created_by=self.user,
        )
        hit = date(2026, 3, 4)
        miss = date(2026, 3, 11)
        self.assertIn(r, reminders_for_date(hit))
        self.assertNotIn(r, reminders_for_date(miss))

    def test_monthly_reschedule_exception(self):
        original = date(2026, 3, 4)
        moved = date(2026, 3, 6)
        r = DayReminder.objects.create(
            title="Měsíční přesun",
            text="M",
            kind=DayReminder.Kind.MONTHLY,
            repeat_monthly={"ordinal": 1, "weekday": 2},
            repeat_active_from=date(2026, 1, 1),
            created_by=self.user,
        )
        self.assertIn(r, reminders_for_date(original))
        DayReminderException.objects.create(
            reminder=r, original_date=original, rescheduled_to=moved
        )
        self.assertNotIn(r, reminders_for_date(original))
        self.assertIn(r, reminders_for_date(moved))

    def test_monthly_outside_active_until(self):
        r = DayReminder.objects.create(
            title="Měsíční konec",
            text="M",
            kind=DayReminder.Kind.MONTHLY,
            repeat_monthly={"ordinal": 1, "weekday": 2},
            repeat_active_from=date(2026, 1, 1),
            repeat_active_until=date(2026, 2, 28),
            created_by=self.user,
        )
        self.assertNotIn(r, reminders_for_date(date(2026, 3, 4)))


class PurgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("purge_u", password="x")

    def test_purge_all_completed(self):
        done = DayReminder.objects.create(
            title="X",
            text="x",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=date(2026, 1, 1),
            completed_at=timezone.now(),
        )
        DayReminder.objects.create(
            title="Y",
            text="y",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=date(2026, 1, 2),
        )
        n = actions.purge_completed(all_completed=True)
        self.assertEqual(n, 1)
        self.assertEqual(DayReminder.objects.filter(completed_at__isnull=False).count(), 0)
        self.assertFalse(DayReminder.objects.filter(pk=done.pk).exists())
        self.assertEqual(DayReminder.objects.filter(title="Y").count(), 1)

    def test_purge_all_completed_deletes_reminder_with_completion(self):
        r = DayReminder.objects.create(
            title="Hotovo checkbox",
            text="x",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=date(2026, 8, 28),
            created_by=self.user,
        )
        DayReminderCompletion.objects.create(reminder=r, resolved_on=date(2026, 8, 28), resolved_by=self.user)
        weekly = DayReminder.objects.create(
            title="Týdenní hotovo",
            text="w",
            kind=DayReminder.Kind.WEEKLY,
            repeat_weekdays=[4],
            created_by=self.user,
        )
        DayReminderCompletion.objects.create(
            reminder=weekly, resolved_on=date(2026, 8, 28), resolved_by=self.user
        )
        open_r = DayReminder.objects.create(
            title="Otevřené",
            text="o",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=date(2026, 8, 28),
            created_by=self.user,
        )
        n = actions.purge_completed(all_completed=True)
        self.assertEqual(n, 2)
        self.assertFalse(DayReminder.objects.filter(pk=r.pk).exists())
        self.assertFalse(DayReminder.objects.filter(pk=weekly.pk).exists())
        self.assertTrue(DayReminder.objects.filter(pk=open_r.pk).exists())
        self.assertEqual(DayReminderCompletion.objects.count(), 0)

    def test_purge_completed_before_keeps_recent_resolved(self):
        old = DayReminder.objects.create(
            title="Staré",
            text="s",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=date(2026, 8, 20),
            created_by=self.user,
        )
        DayReminderCompletion.objects.create(reminder=old, resolved_on=date(2026, 8, 20), resolved_by=self.user)
        recent = DayReminder.objects.create(
            title="Nedávné",
            text="n",
            kind=DayReminder.Kind.WEEKLY,
            repeat_weekdays=[4],
            created_by=self.user,
        )
        DayReminderCompletion.objects.create(
            reminder=recent, resolved_on=date(2026, 9, 4), resolved_by=self.user
        )
        both = DayReminder.objects.create(
            title="Starší i novější",
            text="b",
            kind=DayReminder.Kind.WEEKLY,
            repeat_weekdays=[0, 2, 4],
            created_by=self.user,
        )
        DayReminderCompletion.objects.create(
            reminder=both, resolved_on=date(2026, 8, 28), resolved_by=self.user
        )
        DayReminderCompletion.objects.create(
            reminder=both, resolved_on=date(2026, 9, 1), resolved_by=self.user
        )

        n = actions.purge_completed(all_completed=False, completed_before=date(2026, 8, 31))
        self.assertEqual(n, 1)
        self.assertFalse(DayReminder.objects.filter(pk=old.pk).exists())
        self.assertTrue(DayReminder.objects.filter(pk=recent.pk).exists())
        self.assertTrue(DayReminder.objects.filter(pk=both.pk).exists())
        self.assertTrue(
            DayReminderCompletion.objects.filter(reminder=recent, resolved_on=date(2026, 9, 4)).exists()
        )
        self.assertTrue(
            DayReminderCompletion.objects.filter(reminder=both, resolved_on=date(2026, 9, 1)).exists()
        )

    def test_purge_completed_before_deletes_one_off_by_pinned_date(self):
        orphan = DayReminder.objects.create(
            title="Bez odškrtnutí",
            text="o",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=date(2026, 8, 13),
            created_by=self.user,
        )
        keep_day = DayReminder.objects.create(
            title="Po hranici",
            text="k",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=date(2026, 8, 31),
            created_by=self.user,
        )
        weekly = DayReminder.objects.create(
            title="Týdenní s novějším",
            text="w",
            kind=DayReminder.Kind.WEEKLY,
            repeat_weekdays=[3],
            created_by=self.user,
        )
        DayReminderCompletion.objects.create(
            reminder=weekly, resolved_on=date(2026, 8, 13), resolved_by=self.user
        )
        DayReminderCompletion.objects.create(
            reminder=weekly, resolved_on=date(2026, 9, 3), resolved_by=self.user
        )

        n = actions.purge_completed(all_completed=False, completed_before=date(2026, 8, 31))
        self.assertEqual(n, 1)
        self.assertFalse(DayReminder.objects.filter(pk=orphan.pk).exists())
        self.assertTrue(DayReminder.objects.filter(pk=keep_day.pk).exists())
        self.assertTrue(DayReminder.objects.filter(pk=weekly.pk).exists())
