# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResourceRotationPlan(models.Model):
    """Reusable rotation plan: a matrix of resource code × cycle day.

    Each row is a resource code (A, B, C, ...); each cell maps a day of
    the cycle to a day period, including day-off periods. Rows with the
    same pattern but a different phase let several teams alternate on
    the same post.
    """

    _name = "resource.rotation.plan"
    _description = "Rotation Plan"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    color = fields.Integer()
    tag_ids = fields.Many2many(
        comodel_name="resource.rotation.tag",
        string="Tags",
        help='Organizes rotation plans, e.g. "12-hour", "night work".',
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        index=True,
    )
    description = fields.Text()
    cycle_days = fields.Integer(
        required=True,
        default=7,
        help="Width of the rotation matrix in days.",
    )
    crew_ids = fields.One2many(
        comodel_name="resource.rotation.crew",
        inverse_name="rotation_id",
        string="Resource Codes",
        copy=True,
    )
    crew_count = fields.Integer(compute="_compute_crew_count", string="Crews")
    cell_ids = fields.One2many(
        comodel_name="resource.rotation.cell",
        inverse_name="rotation_id",
        string="Cells",
        copy=True,
    )
    application_ids = fields.One2many(
        comodel_name="resource.rotation.application",
        inverse_name="rotation_id",
        string="Applications",
    )

    @api.depends("crew_ids")
    def _compute_crew_count(self):
        for rotation in self:
            rotation.crew_count = len(rotation.crew_ids)

    cell_count = fields.Integer(compute="_compute_cell_count", string="Cells")

    @api.depends("cell_ids")
    def _compute_cell_count(self):
        for rotation in self:
            rotation.cell_count = len(rotation.cell_ids)

    def action_view_cells(self):
        """Open this plan's matrix cells in their own list/pivot view."""
        return {
            "name": self.env._("Cells"),
            "res_model": "resource.rotation.cell",
            "type": "ir.actions.act_window",
            "view_mode": "list,pivot",
            "domain": [("rotation_id", "in", self.ids)],
            "context": {"default_rotation_id": self[:1].id},
        }

    @api.constrains("cycle_days")
    def _check_cycle_days(self):
        for rotation in self:
            if rotation.cycle_days <= 0:
                raise ValidationError(self.env._("The cycle must be at least one day."))
