# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class ResourcePlanningPeriod(models.Model):
    """A named period of the day, such as Morning, Evening or Night.

    Periods are labels for the day's slots; the concrete times are
    position-specific and live on the schedule lines.
    """

    _name = "resource.planning.period"
    _description = "Period"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        size=8,
        help="Short code shown in rotation matrices and grids, e.g. M or N.",
    )
    active = fields.Boolean(default=True)
    color = fields.Integer()
    is_day_off = fields.Boolean(
        string="Day Off",
        help="Day-off periods mark rest days in rotation matrices.",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        result = super()._compute_display_name()
        # Compact displays (e.g. rotation matrices) render the code
        # instead of the name through `display_period_code` context.
        if self.env.context.get("display_period_code"):
            for period in self:
                if period.code:
                    period.display_name = period.code
        return result
