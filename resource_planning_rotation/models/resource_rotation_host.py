# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResourceRotationHost(models.AbstractModel):
    """Hosts of rotation applications: positions and resources."""

    _name = "resource.rotation.host"
    _description = "Rotation Application Host"

    current_rotation_id = fields.Many2one(
        comodel_name="resource.rotation.plan",
        string="Current Rotation",
        compute="_compute_current_rotation",
        help="The rotation plan in effect today.",
    )

    def _rotation_applications(self):
        """The host's application records; implemented per model."""
        raise NotImplementedError

    def _compute_current_rotation(self):
        today = fields.Date.today()
        for host in self:
            applications = host._rotation_applications().filtered(
                lambda a: a.start_date <= today
                and (not a.end_date or a.end_date >= today)
            )
            host.current_rotation_id = applications.sorted("start_date", reverse=True)[
                :1
            ].rotation_id
