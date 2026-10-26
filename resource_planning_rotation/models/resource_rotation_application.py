# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResourceRotationApplication(models.Model):
    """A rotation plan in effect for a date range.

    Applied directly to a resource (the person's own work pattern);
    the resource_planning_demand_rotation addon adds positions as a second
    parent (crew members then hold the matrix codes).
    """

    _name = "resource.rotation.application"
    _description = "Rotation Application"
    _order = "start_date desc, id"

    resource_id = fields.Many2one(
        comodel_name="resource.resource",
        string="Resource",
        index=True,
        ondelete="cascade",
    )
    rotation_id = fields.Many2one(
        comodel_name="resource.rotation.plan",
        string="Rotation Plan",
        required=True,
        index=True,
        ondelete="restrict",
    )
    start_date = fields.Date(required=True)
    end_date = fields.Date(
        help="Leave empty while the plan applies indefinitely.",
    )
    days_offset = fields.Integer(
        default=0,
        help="Phase shift inside the cycle: on start_date the plan is "
        "already days_offset days in, i.e. cycle day days_offset + 1 "
        "is in effect. E.g. 6 starts a 14-day rotation at its day 7.",
    )
    notes = fields.Char()
    company_id = fields.Many2one(
        comodel_name="res.company",
        compute="_compute_company_id",
        store=True,
        index=True,
    )

    def _rotation_application_parents(self):
        # Parent fields the application can hang from; addons such as
        # resource_planning_demand_rotation extend this with "position_id".
        return ["resource_id"]

    @api.depends("resource_id.company_id")
    def _compute_company_id(self):
        for application in self:
            application.company_id = application.resource_id.company_id

    @api.constrains("resource_id")
    def _check_one_parent(self):
        for application in self:
            parents = application._rotation_application_parents()
            if sum(bool(application[parent]) for parent in parents) != 1:
                raise ValidationError(
                    self.env._("A rotation application needs exactly one parent.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        # Constrains only fire on written fields; every create path
        # (form, RPC, import, o2m) gets the same parent check here.
        parents = self._rotation_application_parents()
        for vals in vals_list:
            if sum(bool(vals.get(parent)) for parent in parents) != 1:
                raise ValidationError(
                    self.env._(
                        "A rotation application needs exactly one parent: "
                        "a position or a resource."
                    )
                )
        return super().create(vals_list)
