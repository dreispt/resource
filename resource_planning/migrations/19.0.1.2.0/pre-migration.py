# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tools.sql import table_exists


def migrate(cr, version):
    # resource.service.position.rotation generalized into
    # resource.service.rotation.application (adds resource parent
    # and members).
    if table_exists(cr, "resource_service_position_rotation") and not table_exists(
        cr, "resource_service_rotation_application"
    ):
        cr.execute(
            "ALTER TABLE resource_service_position_rotation "
            "RENAME TO resource_service_rotation_application"
        )
