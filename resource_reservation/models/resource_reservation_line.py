# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from collections import defaultdict
from datetime import timezone

from odoo import api, fields, models
from odoo.tools.intervals import Intervals


class ResourceReservationLine(models.Model):
    """A leg of a reservation: one required role slot.

    ``resource_id`` may stay empty until the reservation is scheduled;
    auto-assignment then fills it with a matching free resource.
    """

    _name = "resource.reservation.line"
    _description = "Reservation Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    reservation_id = fields.Many2one(
        comodel_name="resource.reservation",
        required=True,
        index=True,
        ondelete="cascade",
    )
    type_leg_id = fields.Many2one(
        comodel_name="resource.reservation.type.leg",
        string="Requirement",
    )
    role_id = fields.Many2one(
        comodel_name="resource.role",
        required=True,
    )
    resource_id = fields.Many2one(
        comodel_name="resource.resource",
        string="Resource",
        index=True,
        domain="[('bookable', '=', True), ('role_ids', 'in', role_id)]",
        help="Leave empty for auto-assignment when the slot is picked.",
    )
    quantity = fields.Integer(
        string="Units",
        default=1,
        help="Pool units consumed. Must be 1 for exclusive resources.",
    )
    name = fields.Char(compute="_compute_name", store=True)
    type_id = fields.Many2one(related="reservation_id.type_id", store=True, index=True)

    @api.depends("role_id", "resource_id")
    def _compute_name(self):
        for line in self:
            line.name = line.resource_id.display_name or line.role_id.display_name

    @api.model
    def _get_busy_intervals(
        self, resources, start_dt, end_dt, exclude_reservation=None
    ):
        """Busy intervals per resource from existing reservations.

        Returns ``{resource_id: Intervals}`` where each interval's
        items are the overlapping `resource.reservation.line` records,
        so callers can sum consumed quantities for pools.

        Stored datetimes are naive UTC; the returned intervals are
        tz-aware UTC so they can be subtracted from calendar work
        intervals.
        """
        start_naive = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
        end_naive = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
        domain = [
            ("resource_id", "in", resources.ids),
            ("reservation_id.active", "=", True),
            ("reservation_id.state", "!=", "cancelled"),
            ("reservation_id.start", "<", end_naive),
            ("reservation_id.stop", ">", start_naive),
        ]
        if exclude_reservation:
            domain.append(("reservation_id", "!=", exclude_reservation.id))
        lines = self.search(domain)
        busy = defaultdict(list)
        for line in lines:
            reservation = line.reservation_id
            busy[line.resource_id.id].append(
                (
                    reservation.start.replace(tzinfo=timezone.utc),
                    reservation.stop.replace(tzinfo=timezone.utc),
                    line,
                )
            )
        return {res_id: Intervals(items) for res_id, items in busy.items()}
