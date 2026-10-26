# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models

RESERVATION_STATES = [
    ("draft", "Draft"),
    ("requested", "Requested"),
    ("scheduled", "Scheduled"),
    ("in_progress", "In progress"),
    ("done", "Done"),
    ("no_show", "No-show"),
    ("cancelled", "Cancelled"),
]


class ResourceReservationStage(models.Model):
    _name = "resource.reservation.stage"
    _description = "Reservation Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    location_id = fields.Many2one(
        comodel_name="res.partner",
        string="Location",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('is_resource_location', '=', True)]",
        help="The site owning this pipeline stage.",
    )
    state = fields.Selection(
        selection=RESERVATION_STATES,
        required=True,
        default="draft",
        index=True,
        help="Fixed state this stage maps to. Automation and reporting "
        "rely on states, not on the configurable stage names.",
    )
    fold = fields.Boolean(
        string="Folded in Kanban",
        help="Fold this stage by default in kanban views.",
    )
