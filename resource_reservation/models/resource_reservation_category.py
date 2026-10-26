# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResourceReservationCategory(models.Model):
    _name = "resource.reservation.category"
    _description = "Reservation Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer()
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        index=True,
    )
    type_ids = fields.One2many(
        comodel_name="resource.reservation.type",
        inverse_name="category_id",
        string="Reservation Types",
    )
