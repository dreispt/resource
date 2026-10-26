# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import datetime, time, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class PlanningCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Role = cls.env["resource.role"]
        cls.Assignment = cls.env["resource.service.assignment"]
        cls.Resource = cls.env["resource.resource"]
        cls.Calendar = cls.env["resource.calendar"]
        cls.Partner = cls.env["res.partner"]
        cls.period_morning = cls.env.ref("resource_planning.period_morning")
        cls.period_evening = cls.env.ref("resource_planning.period_evening")
        cls.period_night = cls.env.ref("resource_planning.period_night")

        cls.calendar = cls.Calendar.create(
            {
                "name": "Mon-Fri 9-17 UTC",
                "tz": "UTC",
                "attendance_ids": [
                    fields.Command.create(
                        {
                            "name": f"{day} 9-17",
                            "dayofweek": str(day),
                            "day_period": "morning",
                            "hour_from": 9,
                            "hour_to": 17,
                        }
                    )
                    for day in range(5)
                ],
            }
        )
        cls.role = cls.Role.create({"name": "Technician"})
        cls.role_supervisor = cls.Role.create({"name": "Supervisor"})
        cls.crew_a = cls.Resource.create(
            {
                "name": "Crew A",
                "resource_type": "material",
                "role_ids": [fields.Command.set(cls.role.ids)],
            }
        )
        cls.crew_b = cls.Resource.create(
            {
                "name": "Crew B",
                "resource_type": "material",
                "role_ids": [fields.Command.set(cls.role.ids)],
            }
        )
        # Monday of this week: a deterministic anchor for recurrences.
        today = fields.Date.today()
        cls.monday = today - timedelta(days=today.weekday())

    def _dt(self, day, hour):
        """Naive UTC datetime at `hour` on `date`."""
        return datetime.combine(day, time(hour))
