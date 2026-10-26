# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class ResourceResource(models.Model):
    _inherit = "resource.resource"

    service_assignment_ids = fields.One2many(
        comodel_name="resource.service.assignment",
        inverse_name="resource_id",
        string="Service Assignments",
    )
    service_assignment_count = fields.Integer(
        compute="_compute_service_assignment_count"
    )

    @api.depends("service_assignment_ids")
    def _compute_service_assignment_count(self):
        for resource in self:
            resource.service_assignment_count = len(resource.service_assignment_ids)

    def action_view_service_assignments(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "resource_planning.action_resource_service_assignment"
        )
        action["domain"] = [("resource_id", "in", self.ids)]
        action["context"] = {"default_resource_id": self[:1].id}
        return action
