# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    stage_ids = fields.One2many(
        comodel_name="resource.reservation.stage",
        inverse_name="location_id",
        string="Stage Pipeline",
        copy=True,
        help="Ordered pipeline stages for reservations at this "
        "location. Each maps to a fixed state.",
    )
    reservation_ids = fields.One2many(
        comodel_name="resource.reservation",
        inverse_name="location_id",
        string="Reservations",
    )
    reservation_count = fields.Integer(compute="_compute_reservation_count")

    def _compute_reservation_count(self):
        counts = dict(
            self.env["resource.reservation"]._read_group(
                [("location_id", "in", self.ids)], ["location_id"], ["__count"]
            )
        )
        for partner in self:
            partner.reservation_count = counts.get(partner, 0)

    def _get_reservation_stage(self, state):
        """First stage of this location's pipeline mapped to `state`."""
        return self.stage_ids.filtered(lambda s: s.state == state)[:1]

    def action_open_reservations(self):
        """Open this location's reservations board (kanban by stage)."""
        return {
            "domain": [("location_id", "in", self.ids)],
            "context": {"search_default_group_stage": 1},
            "name": self.env._("Reservations"),
            "res_model": "resource.reservation",
            "type": "ir.actions.act_window",
            "view_mode": "kanban,list,calendar,form",
        }

    def action_open_checkins(self):
        """Open this location's upcoming reservations (check-ins)."""
        return {
            "domain": [("location_id", "in", self.ids)],
            "context": {"search_default_upcoming": 1},
            "name": self.env._("Check-ins"),
            "res_model": "resource.reservation",
            "type": "ir.actions.act_window",
            "view_mode": "kanban,list,calendar,form",
        }
