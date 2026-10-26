# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta, timezone

from odoo import fields

from .common import ReservationCommon


def _naive_utc(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class TestAvailability(ReservationCommon):
    def _slots_for_week(self, type_=None, **kwargs):
        type_ = type_ or self.type
        now = fields.Datetime.now()
        return type_._get_available_slots(
            now + timedelta(days=1),
            now + timedelta(days=14),
            location_id=kwargs.get("location_id", self.location.id),
            guests=kwargs.get("guests", 1),
        )

    def test_slots_within_schedule(self):
        """Slots exist on workdays inside attendance, none on Sundays."""
        slots = self._slots_for_week()
        self.assertTrue(slots)
        sunday = self._next_weekday(6).date()
        self.assertNotIn(sunday, slots)
        monday = self._next_weekday(0).date()
        self.assertIn(monday, slots)
        monday_slots = slots[monday]
        # First slot at 9:00, none starting before 9:00 or ending past 18:00
        self.assertEqual(monday_slots[0].hour, 9)
        self.assertTrue(all(9 <= s.hour < 18 for s in monday_slots))

    def test_leave_blocks_resource(self):
        """A resource leave removes its slots."""
        monday = self._next_weekday(0)
        self.Leave.create(
            {
                "name": "Day off",
                "resource_id": self.resource.id,
                "calendar_id": self.calendar.id,
                "date_from": monday,
                "date_to": monday + timedelta(hours=9),
                "time_type": "leave",
            }
        )
        slots = self._slots_for_week()
        self.assertNotIn(monday.date(), slots)
        self.assertIn(self._next_weekday(1).date(), slots)

    def test_booking_blocks_resource(self):
        """An existing reservation removes overlapping slots."""
        monday = self._next_weekday(0)  # 9:00-10:00
        reservation = self._make_reservation(start=monday)
        reservation.action_schedule()
        self.assertEqual(reservation.state, "scheduled")
        slots = self._slots_for_week()
        monday_slots = slots[monday.date()]
        # 9:00 and 9:30 overlap the booking; 10:00 is free again
        self.assertNotIn(9, [s.hour for s in monday_slots])
        self.assertTrue(all(s.hour != 9 or s.minute != 30 for s in monday_slots))
        self.assertIn(10, [s.hour for s in monday_slots])

    def test_pool_allows_simultaneous(self):
        """A pool with qty 2 serves two bookings at the same slot."""
        monday = self._next_weekday(0)
        for _i in range(2):
            reservation = self._make_reservation(
                type_id=self.pool_type.id, start=monday
            )
            reservation.action_schedule()
        slots = self._slots_for_week(type_=self.pool_type)
        # qty=2, consumed=2 → the same slot is exhausted, the day isn't.
        monday_hours = [s.hour for s in slots[monday.date()]]
        self.assertNotIn(9, monday_hours)
        self.assertIn(10, monday_hours)

    def test_pool_guests_quantity(self):
        """Party size drives unit consumption on pools."""
        monday = self._next_weekday(0)
        # one reservation for 2 guests consumes the whole qty=2 pool
        reservation = self._make_reservation(
            type_id=self.pool_type.id, start=monday, guests=2
        )
        reservation.action_schedule()
        self.assertEqual(reservation.line_ids.quantity, 2)
        slots = self._slots_for_week(type_=self.pool_type)
        monday_hours = [s.hour for s in slots[monday.date()]]
        self.assertNotIn(9, monday_hours)
        self.assertIn(10, monday_hours)

    def test_multi_leg_requires_all(self):
        """A type with two legs offers slots only if both are fillable."""
        consult = self.Type.create(
            {
                "name": "Two-leg type",
                "category_id": self.category.id,
                "duration": 1.0,
                "slot_duration": 0.5,
                "reservation_calendar_id": self.calendar.id,
                "location_ids": [fields.Command.set(self.location.ids)],
                "leg_ids": [
                    fields.Command.create(
                        {"role_id": self.function.id, "sequence": 10}
                    ),
                    fields.Command.create(
                        {
                            "role_id": self.function_room.id,
                            "sequence": 20,
                        }
                    ),
                ],
            }
        )
        slots = self._slots_for_week(type_=consult)
        self.assertTrue(slots)
        # Remove the only room candidate: a leave covering the window
        now = fields.Datetime.now()
        self.Leave.create(
            {
                "name": "Renovation",
                "resource_id": self.room.id,
                "calendar_id": self.calendar.id,
                "date_from": now,
                "date_to": now + timedelta(days=30),
                "time_type": "leave",
            }
        )
        slots = self._slots_for_week(type_=consult)
        self.assertFalse(slots, "room unavailable → no slot offered for the type")

    def test_location_schedule_restricts(self):
        """A resource's location presence filters its slots."""
        # Presence only on Mondays
        monday_only = self.Calendar.create(
            {
                "name": "Monday only",
                "tz": "UTC",
                "attendance_ids": [
                    fields.Command.create(
                        {
                            "name": "Monday",
                            "dayofweek": "0",
                            "day_period": "morning",
                            "hour_from": 9,
                            "hour_to": 18,
                        }
                    )
                ],
            }
        )
        self.resource.presence_ids = [
            fields.Command.clear(),
            fields.Command.create(
                {
                    "location_id": self.location.id,
                    "calendar_id": monday_only.id,
                }
            ),
        ]
        slots = self._slots_for_week()
        monday = self._next_weekday(0).date()
        tuesday = self._next_weekday(1).date()
        self.assertIn(monday, slots)
        self.assertNotIn(tuesday, slots)

    def test_multi_day_duration(self):
        """Durations may span days when calendars allow."""
        allday = self.Calendar.create(
            {
                "name": "Continuous",
                "tz": "UTC",
                "attendance_ids": [
                    fields.Command.create(
                        {
                            "name": f"Day {day}",
                            "dayofweek": str(day),
                            "day_period": "morning",
                            "hour_from": 0,
                            "hour_to": 24,
                        }
                    )
                    for day in range(7)
                ],
            }
        )
        self.resource.calendar_id = allday
        stay_type = self.Type.create(
            {
                "name": "Stay",
                "category_id": self.category.id,
                "duration": 20.0,
                "slot_duration": 24.0,
                "reservation_calendar_id": allday.id,
                "location_ids": [fields.Command.set(self.location.ids)],
                "leg_ids": [fields.Command.create({"role_id": self.function.id})],
            }
        )
        slots = self._slots_for_week(type_=stay_type)
        self.assertTrue(slots)
        reservation = self._make_reservation(
            type_id=stay_type.id, start=self._next_weekday(0)
        )
        reservation.action_schedule()
        self.assertEqual(reservation.state, "scheduled")
        self.assertEqual(reservation.stop, reservation.start + timedelta(hours=20))

    def test_no_candidates_no_slots(self):
        """A leg without matching resources blocks all slots."""
        lonely = self.Type.create(
            {
                "name": "No candidates",
                "category_id": self.category.id,
                "duration": 1.0,
                "reservation_calendar_id": self.calendar.id,
                "leg_ids": [
                    fields.Command.create(
                        {
                            "role_id": self.Function.create(
                                {"name": "Nothing provides this"}
                            ).id
                        }
                    )
                ],
            }
        )
        slots = self._slots_for_week(type_=lonely)
        self.assertFalse(slots)

    def test_busy_intervals_exclude_cancelled(self):
        """Cancelled reservations free their span again."""
        monday = self._next_weekday(0)
        reservation = self._make_reservation(start=monday)
        reservation.action_schedule()
        slots = self._slots_for_week()
        self.assertNotIn(9, [s.hour for s in slots[monday.date()]])
        reservation.action_cancel()
        slots = self._slots_for_week()
        self.assertIn(9, [s.hour for s in slots[monday.date()]])
