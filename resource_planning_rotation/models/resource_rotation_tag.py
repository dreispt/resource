# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResourceRotationTag(models.Model):
    """Tags for organizing rotation plans, e.g. "12-hour"."""

    _name = "resource.rotation.tag"
    _description = "Rotation Plan Tag"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    color = fields.Integer()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "The tag name must be unique."),
    ]
