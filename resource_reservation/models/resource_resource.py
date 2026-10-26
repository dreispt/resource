# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResourceResource(models.Model):
    _inherit = "resource.resource"

    bookable = fields.Boolean(
        string="Reservable",
        help="Offer this resource for reservations.",
    )
    sequence = fields.Integer(
        default=10,
        help="Ordering for auto-assignment and pick lists. "
        "Higher values are deprioritized.",
    )
    quantity = fields.Integer(
        string="Pool Quantity",
        default=1,
        help="Units available for simultaneous booking. "
        "1 = exclusive resource; more = a pool of interchangeable units.",
    )

    _check_reservation_quantity = models.Constraint(
        "CHECK(quantity >= 1)",
        "Pool quantity must be at least 1.",
    )
