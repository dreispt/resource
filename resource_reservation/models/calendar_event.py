# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    reservation_ids = fields.One2many(
        comodel_name="resource.reservation",
        inverse_name="meeting_id",
        string="Reservations",
    )
