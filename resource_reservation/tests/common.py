# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class ReservationCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Category = cls.env["resource.reservation.category"]
        cls.Stage = cls.env["resource.reservation.stage"]
        cls.Function = cls.env["resource.role"]
        cls.Type = cls.env["resource.reservation.type"]
        cls.TypeLeg = cls.env["resource.reservation.type.leg"]
        cls.Reservation = cls.env["resource.reservation"]
        cls.Line = cls.env["resource.reservation.line"]
        cls.Resource = cls.env["resource.resource"]
        cls.Calendar = cls.env["resource.calendar"]
        cls.Leave = cls.env["resource.calendar.leaves"]
        cls.Partner = cls.env["res.partner"]

        cls.calendar = cls.Calendar.create(
            {
                "name": "Mon-Fri 9-18 UTC",
                "tz": "UTC",
                "attendance_ids": [
                    fields.Command.create(
                        {
                            "name": f"{day} morning",
                            "dayofweek": str(day),
                            "day_period": "morning",
                            "hour_from": 9,
                            "hour_to": 13,
                        }
                    )
                    for day in range(5)
                ]
                + [
                    fields.Command.create(
                        {
                            "name": f"{day} afternoon",
                            "dayofweek": str(day),
                            "day_period": "afternoon",
                            "hour_from": 14,
                            "hour_to": 18,
                        }
                    )
                    for day in range(5)
                ],
            }
        )
        cls.category = cls.Category.create({"name": "Test category"})
        cls.location = cls.Partner.create(
            {
                "name": "Test Site",
                "is_company": True,
                "is_resource_location": True,
                "tz": "UTC",
            }
        )
        cls.stages = {}
        stage_defs = [
            ("draft", "Requested", "draft"),
            ("scheduled", "Scheduled", "scheduled"),
            ("confirmed", "Confirmed", "scheduled"),
            ("in_progress", "In progress", "in_progress"),
            ("done", "Done", "done"),
            ("no_show", "No-show", "no_show"),
            ("cancelled", "Cancelled", "cancelled"),
        ]
        for sequence, (key, label, state) in enumerate(stage_defs):
            cls.stages[key] = cls.Stage.create(
                {
                    "name": label,
                    "location_id": cls.location.id,
                    "state": state,
                    "sequence": (sequence + 1) * 10,
                }
            )
        cls.function = cls.Function.create({"name": "Test function"})
        cls.function_room = cls.Function.create({"name": "Test room"})
        cls.function_pool = cls.Function.create({"name": "Test pool seats"})
        cls.resource = cls.Resource.create(
            {
                "name": "Test staff",
                "resource_type": "user",
                "bookable": True,
                "role_ids": [fields.Command.set(cls.function.ids)],
                "calendar_id": cls.calendar.id,
                "presence_ids": [
                    fields.Command.create({"location_id": cls.location.id})
                ],
            }
        )
        cls.room = cls.Resource.create(
            {
                "name": "Test room",
                "resource_type": "material",
                "bookable": True,
                "role_ids": [fields.Command.set(cls.function_room.ids)],
                "calendar_id": cls.calendar.id,
                "presence_ids": [
                    fields.Command.create({"location_id": cls.location.id})
                ],
            }
        )
        cls.pool = cls.Resource.create(
            {
                "name": "Test pool",
                "resource_type": "material",
                "bookable": True,
                "quantity": 2,
                "role_ids": [fields.Command.set(cls.function_pool.ids)],
                "calendar_id": cls.calendar.id,
                "presence_ids": [
                    fields.Command.create({"location_id": cls.location.id})
                ],
            }
        )
        cls.pool_type = cls.Type.create(
            {
                "name": "Pool type",
                "category_id": cls.category.id,
                "duration": 1.0,
                "slot_duration": 0.5,
                "reservation_calendar_id": cls.calendar.id,
                "location_ids": [fields.Command.set(cls.location.ids)],
                "leg_ids": [fields.Command.create({"role_id": cls.function_pool.id})],
            }
        )
        cls.type = cls.Type.create(
            {
                "name": "Test type",
                "category_id": cls.category.id,
                "duration": 1.0,
                "slot_duration": 0.5,
                "reservation_calendar_id": cls.calendar.id,
                "location_ids": [fields.Command.set(cls.location.ids)],
                "leg_ids": [fields.Command.create({"role_id": cls.function.id})],
            }
        )
        cls.customer = cls.Partner.create({"name": "Test Customer"})

    def _next_weekday(self, weekday, days_ahead=0):
        """A naive UTC datetime at 9:00 on the given weekday, `days_ahead` out."""
        today = fields.Datetime.now()
        delta = (weekday - today.weekday()) % 7 or 7
        start = today + timedelta(days=delta + days_ahead)
        return start.replace(hour=9, minute=0, second=0, microsecond=0)

    def _make_reservation(self, **kwargs):
        vals = {
            "partner_id": self.customer.id,
            "type_id": self.type.id,
            "location_id": self.location.id,
        }
        vals.update(kwargs)
        return self.Reservation.create(vals)
