# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError

from .common import ReservationCommon


class TestLifecycle(ReservationCommon):
    def test_legs_auto_created(self):
        """Creating a reservation populates legs from the type."""
        reservation = self._make_reservation()
        self.assertEqual(len(reservation.line_ids), 1)
        self.assertEqual(reservation.line_ids.role_id, self.function)
        self.assertFalse(reservation.line_ids.resource_id)
        self.assertEqual(reservation.state, "requested")
        self.assertEqual(reservation.stage_id, self.stages["requested"])

    def test_schedule_assigns_and_creates_event(self):
        """Scheduling assigns resources and syncs a calendar event."""
        monday = self._next_weekday(0)
        reservation = self._make_reservation(start=monday)
        reservation.action_schedule()
        self.assertEqual(reservation.state, "scheduled")
        self.assertEqual(reservation.stage_id, self.stages["scheduled"])
        self.assertEqual(reservation.line_ids.resource_id, self.resource)
        self.assertTrue(reservation.meeting_id)
        self.assertEqual(reservation.meeting_id.start, monday)
        self.assertEqual(reservation.meeting_id.stop, monday + timedelta(hours=1))

    def test_confirm_attend_noshow(self):
        """Confirmation advances the stage; the fixed state stays."""
        reservation = self._make_reservation(start=self._next_weekday(0))
        reservation.action_schedule()
        reservation.action_confirm()
        self.assertEqual(reservation.state, "scheduled")
        self.assertEqual(reservation.stage_id, self.stages["confirmed"])
        reservation.action_attend()
        self.assertEqual(reservation.state, "in_progress")
        self.assertEqual(reservation.stage_id, self.stages["in_progress"])
        reservation.action_return()
        self.assertEqual(reservation.state, "done")
        self.assertEqual(reservation.stage_id, self.stages["done"])

    def test_cancel_removes_event(self):
        """Cancelling archives the record and drops the event."""
        reservation = self._make_reservation(start=self._next_weekday(0))
        reservation.action_schedule()
        event = reservation.meeting_id
        self.assertTrue(event.exists())
        reservation.action_cancel()
        self.assertEqual(reservation.state, "cancelled")
        self.assertFalse(reservation.active)
        self.assertFalse(event.exists())

    def test_unschedule_resets(self):
        """Unscheduling clears slot, resources and event."""
        reservation = self._make_reservation(start=self._next_weekday(0))
        reservation.action_schedule()
        reservation.action_unschedule()
        self.assertEqual(reservation.state, "requested")
        self.assertFalse(reservation.start)
        self.assertFalse(reservation.line_ids.resource_id)
        self.assertFalse(reservation.meeting_id)

    def test_double_booking_raises(self):
        """The same exclusive resource can't be booked twice."""
        monday = self._next_weekday(0)
        first = self._make_reservation(start=monday)
        first.action_schedule()
        second = self._make_reservation(start=monday)
        with self.assertRaises(ValidationError):
            second.action_schedule()

    def test_fixed_resource_conflict_raises(self):
        """Manually assigned resources are conflict-checked."""
        monday = self._next_weekday(0)
        first = self._make_reservation(start=monday)
        first.line_ids.resource_id = self.resource
        first.action_schedule()
        second = self._make_reservation(start=monday)
        second.line_ids.resource_id = self.resource
        with self.assertRaises(ValidationError):
            second.action_schedule()

    def test_reschedule_frees_old_span(self):
        """Rescheduling doesn't conflict with the reservation itself."""
        monday = self._next_weekday(0)
        tuesday = self._next_weekday(1)
        reservation = self._make_reservation(start=monday)
        reservation.action_schedule()
        reservation.start = tuesday
        reservation.action_confirm()
        self.assertEqual(reservation.meeting_id.start, tuesday)

    def test_out_flow_states(self):
        """OUT reservations move through pickup/return."""
        rental_category = self.Category.create({"name": "Rentals"})
        for key, label in [
            ("requested", "Requested"),
            ("scheduled", "Booked"),
            ("scheduled", "Confirmed"),
            ("in_progress", "Picked up"),
            ("done", "Returned"),
            ("cancelled", "Cancelled"),
        ]:
            self.Stage.create(
                {
                    "name": label,
                    "location_id": self.location.id,
                    "state": key,
                }
            )
        rental_type = self.Type.create(
            {
                "name": "Rental",
                "category_id": rental_category.id,
                "flow": "out",
                "duration": 1.0,
                "reservation_calendar_id": self.calendar.id,
                "leg_ids": [fields.Command.create({"role_id": self.function_room.id})],
            }
        )
        reservation = self._make_reservation(
            type_id=rental_type.id, start=self._next_weekday(0)
        )
        reservation.action_schedule()
        reservation.action_pick_up()
        self.assertEqual(reservation.state, "in_progress")
        reservation.action_return()
        self.assertEqual(reservation.state, "done")

    def test_hold_blocks_and_expires(self):
        """A draft hold consumes the slot; expiry releases it."""
        monday = self._next_weekday(0)
        hold = self._make_reservation(start=monday, state="draft")
        self.assertTrue(hold.type_id.hold_duration)
        hold.hold_expiration = fields.Datetime.now() + timedelta(minutes=15)
        hold.line_ids.resource_id = self.resource
        other = self._make_reservation(start=monday)
        with self.assertRaises(ValidationError):
            other.action_schedule()
        # cancelling the hold releases the slot
        hold.action_cancel()
        other.action_schedule()
        self.assertEqual(other.state, "scheduled")

    def test_hold_extend_and_schedule_clears(self):
        """'I need more time' restarts the countdown; scheduling ends it."""
        monday = self._next_weekday(0)
        hold = self._make_reservation(start=monday)
        hold.hold_expiration = fields.Datetime.now() + timedelta(minutes=2)
        hold.action_extend_hold()
        self.assertGreater(
            hold.hold_expiration,
            fields.Datetime.now() + timedelta(minutes=10),
        )
        hold.action_schedule()
        self.assertFalse(hold.hold_expiration)
        self.assertFalse(hold.is_hold)

    def test_cron_releases_expired_holds(self):
        """The cleanup cron cancels drafts past their hold deadline."""
        monday = self._next_weekday(0)
        hold = self._make_reservation(start=monday, state="draft")
        hold.hold_expiration = fields.Datetime.now() - timedelta(minutes=1)
        self.env["resource.reservation"]._cron_expire_holds()
        self.assertEqual(hold.state, "cancelled")
