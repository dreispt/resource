# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Resource Planning",
    "summary": "Assign generic resources to time intervals — the planning base",
    "version": "19.0.1.2.0",
    "development_status": "Alpha",
    "category": "Services",
    "website": "https://github.com/OCA/resource",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "maintainers": ["dreispt"],
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "resource",
        "resource_location",
        "resource_role",
    ],
    "data": [
        "security/resource_planning_security.xml",
        "security/ir.model.access.csv",
        "data/resource_planning_periods.xml",
        "views/resource_planning_period_views.xml",
        "views/resource_planning_assignment_views.xml",
        "views/resource_resource_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "demo/resource_planning_demo.xml",
    ],
}
