# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Resource Reservation",
    "summary": "Book resources for time slots: appointments, stays and rentals",
    "version": "19.0.1.2.0",
    "development_status": "Alpha",
    "category": "Appointments",
    "website": "https://github.com/OCA/resource",
    "author": "Daniel Reis, Odoo Community Association (OCA)",
    "maintainers": ["dreispt"],
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "calendar",
        "mail",
        "portal",
        "resource",
        "resource_location",
        "resource_role",
    ],
    "data": [
        "security/resource_reservation_security.xml",
        "data/ir_cron.xml",
        "security/ir.model.access.csv",
        "templates/reservation.xml",
        "views/res_partner_views.xml",
        "views/resource_reservation_category_views.xml",
        "views/resource_reservation_type_views.xml",
        "views/resource_reservation_views.xml",
        "views/resource_resource_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "demo/resource_reservation_demo.xml",
    ],
}
