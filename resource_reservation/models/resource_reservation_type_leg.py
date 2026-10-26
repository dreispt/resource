# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResourceReservationTypeLeg(models.Model):
    """A required role of a reservation type.

    Each leg is a standin for one resource to be reserved: booking the
    type reserves a resource carrying ``role_id``.
    """

    _name = "resource.reservation.type.leg"
    _description = "Reservation Type Leg"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    type_id = fields.Many2one(
        comodel_name="resource.reservation.type",
        required=True,
        index=True,
        ondelete="cascade",
    )
    role_id = fields.Many2one(
        comodel_name="resource.role",
        required=True,
    )
    quantity = fields.Integer(
        string="Units",
        default=1,
        help="Units of a pool resource consumed per booking. "
        "For seat pools, the reservation's guest count applies "
        "instead when higher.",
    )
