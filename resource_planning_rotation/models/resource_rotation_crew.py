# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResourceRotationCrew(models.Model):
    """One crew in a rotation matrix (usually a letter: A, B, C).

    Each row is an identity within the crew — e.g. team A — whose cells
    map every day of the cycle to a period.
    """

    _name = "resource.rotation.crew"
    _description = "Rotation Crew"
    _rec_name = "code"
    _order = "rotation_id, sequence, id"

    rotation_id = fields.Many2one(
        comodel_name="resource.rotation.plan",
        string="Rotation",
        required=True,
        index=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    code = fields.Char(
        required=True,
        help="Resource code, usually a letter: A, B, C, ...",
    )
    cell_ids = fields.One2many(
        comodel_name="resource.rotation.cell",
        inverse_name="crew_id",
        string="Cells",
        copy=True,
    )
    company_id = fields.Many2one(
        related="rotation_id.company_id",
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            "code_uniq",
            "unique(rotation_id, code)",
            "Resource codes must be unique within a rotation.",
        ),
    ]
