# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResourceRotationCell(models.Model):
    """A rotation matrix cell: resource code × day → day period.

    The period decides what happens that day — a work period or a
    day-off period (`resource.period.is_day_off`).
    """

    _name = "resource.rotation.cell"
    _description = "Rotation Cell"
    _order = "rotation_id, crew_id, day"

    def _compute_display_name(self):
        # Cells display as the day period's short code, e.g. "M".
        for cell in self:
            cell.display_name = cell.period_id.code or cell.period_id.name

    rotation_id = fields.Many2one(
        comodel_name="resource.rotation.plan",
        string="Rotation",
        compute="_compute_rotation_id",
        store=True,
        index=True,
        ondelete="cascade",
    )
    crew_id = fields.Many2one(
        comodel_name="resource.rotation.crew",
        string="Resource",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('rotation_id', '=', rotation_id)]",
    )
    day = fields.Integer(
        required=True,
        default=1,
        help="Day of the cycle, starting at 1.",
    )
    period_id = fields.Many2one(
        comodel_name="resource.planning.period",
        string="Period",
        required=True,
        index=True,
    )
    period_code = fields.Char(
        related="period_id.code",
        string="Code",
    )
    is_day_off = fields.Boolean(
        related="period_id.is_day_off",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="rotation_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("crew_id.rotation_id")
    def _compute_rotation_id(self):
        # Cells are also created through the row, which carries the
        # rotation; keep the flat link consistent either way.
        for cell in self:
            cell.rotation_id = cell.crew_id.rotation_id

    _sql_constraints = [
        (
            "row_day_uniq",
            "unique(crew_id, day)",
            "Each resource code has one period per day.",
        ),
    ]

    @api.constrains("day", "rotation_id")
    def _check_day_in_cycle(self):
        for cell in self:
            days = cell.rotation_id.cycle_days
            if not 1 <= cell.day <= days:
                raise ValidationError(
                    self.env._(
                        "Day %(day)s is outside the %(days)s-day cycle.",
                        day=cell.day,
                        days=days,
                    )
                )
