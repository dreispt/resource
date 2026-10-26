# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import PlanningCommon


@tagged("post_install", "-at_install")
class TestAssignment(PlanningCommon):
    def test_ad_hoc_assignment_lifecycle(self):
        """A crew is booked for an ad hoc job: no schedule needed.

        The planner creates the assignment directly, plans it, publishes
        it and later marks it done.
        """
        start = self._dt(self.monday + timedelta(days=7), 9)
        assignment = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": start,
                "end_datetime": start + timedelta(hours=8),
            }
        )
        self.assertEqual(assignment.state, "draft")
        assignment.action_plan()
        self.assertEqual(assignment.state, "planned")
        assignment.action_publish()
        self.assertEqual(assignment.state, "published")
        assignment.action_complete()
        self.assertEqual(assignment.state, "completed")

    def test_overlapping_assignment_is_blocked(self):
        """A resource cannot be double-booked once work is planned.

        A draft may overlap while the planner decides, but planning or
        publishing a second overlapping assignment is refused.
        """
        start = self._dt(self.monday + timedelta(days=7), 9)
        first = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": start,
                "end_datetime": start + timedelta(hours=8),
            }
        )
        first.action_plan()
        overlapping = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": start + timedelta(hours=4),
                "end_datetime": start + timedelta(hours=12),
            }
        )
        self.assertTrue(overlapping.has_conflicts)
        with self.assertRaises(ValidationError):
            overlapping.action_plan()
        self.assertEqual(overlapping.state, "draft")

    def test_adjacent_assignments_do_not_conflict(self):
        """Ending and starting at the same instant is fine: half-open."""
        start = self._dt(self.monday + timedelta(days=7), 9)
        first = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": start,
                "end_datetime": start + timedelta(hours=4),
            }
        )
        first.action_plan()
        second = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": start + timedelta(hours=4),
                "end_datetime": start + timedelta(hours=8),
            }
        )
        second.action_publish()
        self.assertEqual(second.state, "published")

    def test_cancelled_assignment_frees_the_slot(self):
        """Cancelling an assignment releases the resource's time."""
        start = self._dt(self.monday + timedelta(days=7), 9)
        first = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": start,
                "end_datetime": start + timedelta(hours=8),
            }
        )
        first.action_plan()
        first.action_cancel()
        second = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": start,
                "end_datetime": start + timedelta(hours=8),
            }
        )
        second.action_publish()
        self.assertEqual(second.state, "published")

    def test_archived_resource_cannot_be_planned(self):
        """An archived resource refuses new planned work."""
        self.crew_a.active = False
        assignment = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,
                "start_datetime": self._dt(self.monday + timedelta(days=7), 9),
                "end_datetime": self._dt(self.monday + timedelta(days=7), 17),
            }
        )
        with self.assertRaises(ValidationError):
            assignment.action_plan()

    def test_role_mismatch_is_a_warning(self):
        """A resource outside the required role warns but stays plannable."""
        start = self._dt(self.monday + timedelta(days=7), 9)
        assignment = self.Assignment.create(
            {
                "resource_id": self.crew_a.id,  # declared "Technician" only
                "role_id": self.role_supervisor.id,
                "start_datetime": start,
                "end_datetime": start + timedelta(hours=8),
            }
        )
        self.assertIn("Supervisor", assignment.warning_message)
        assignment.action_publish()
        self.assertEqual(assignment.state, "published")

    def test_outside_working_calendar_is_a_warning(self):
        """Work outside the resource's calendar warns the planner."""
        crew = self.Resource.create(
            {"name": "Crew on shifts", "calendar_id": self.calendar.id}
        )
        sunday = self.monday + timedelta(days=13)
        assignment = self.Assignment.create(
            {
                "resource_id": crew.id,
                "start_datetime": self._dt(sunday, 9),
                "end_datetime": self._dt(sunday, 17),
            }
        )
        self.assertIn("working calendar", assignment.warning_message)

    def test_backwards_interval_is_rejected(self):
        """The end must be later than the start."""
        with self.assertRaises(ValidationError):
            self.Assignment.create(
                {
                    "resource_id": self.crew_a.id,
                    "start_datetime": self._dt(self.monday, 17),
                    "end_datetime": self._dt(self.monday, 9),
                }
            )
