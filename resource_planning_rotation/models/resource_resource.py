# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class ResourceResource(models.Model):
    _inherit = ["resource.resource", "resource.rotation.host"]

    rotation_application_ids = fields.One2many(
        comodel_name="resource.rotation.application",
        inverse_name="resource_id",
        string="Rotation Plans",
        help="Rotation plans applied directly to this resource.",
    )

    rotation_application_count = fields.Integer(
        compute="_compute_rotation_application_count",
        string="Rotation Plans",
    )

    @api.depends("rotation_application_ids")
    def _compute_rotation_application_count(self):
        for resource in self:
            resource.rotation_application_count = len(resource.rotation_application_ids)

    def _rotation_applications(self):
        return self.rotation_application_ids

    def action_view_rotation_applications(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Rotation Plans",
            "res_model": "resource.rotation.application",
            "view_mode": "list",
            "domain": [("resource_id", "in", self.ids)],
            "context": {"default_resource_id": self[:1].id},
        }
