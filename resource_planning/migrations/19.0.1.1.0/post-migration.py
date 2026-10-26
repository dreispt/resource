# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import SUPERUSER_ID, api, fields

# Backfill rotation matrices for plans installed before the matrix
# model replaced the step lines. Rotations that already have rows are
# left untouched.

PERIODS = {
    "M": "period_morning",
    "A": "period_afternoon",
    "D": "period_day",
    "E": "period_evening",
    "N": "period_night",
    "O": "period_off",
}

PATTERNS = {
    "rotation_5on_2off": {"A": "DDDDDOO"},
    "rotation_4on_4off": {"A": "DDDDOOOO"},
    "rotation_6on_4off": {"A": "DDDDDDOOOO"},
    "rotation_7on_7off": {"A": "D" * 7 + "O" * 7},
    "rotation_14on_14off": {"A": "D" * 14 + "O" * 14},
    "rotation_alternating_shifts": {"A": "M" * 7 + "E" * 7 + "N" * 7 + "O" * 7},
    "rotation_rapid_3shift": {"A": "MMEENNOO"},
    "rotation_weekday_cycle": {"A": "M" * 5 + "OO" + "E" * 5 + "OO" + "N" * 5 + "OO"},
    "rotation_2_2_3": {"A": "DDOODDDOODDOOO"},
    "rotation_pitman": {"A": "DDOODDDOODDOOO"},
    "rotation_dupont": {"A": "NNNNOOODDDONNNOOODDDDOOOOOOO"},
    "rotation_4days_4nights": {"A": "DDDDNNNNOOOO"},
    "rotation_4crew_8h": {
        "A": "MMEENNOO",
        "B": "OOMMEENN",
        "C": "NNOOMMEE",
        "D": "EENNOOMM",
    },
    "rotation_24on_48off": {"A": "DOO"},
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "resource.service.rotation" not in env:
        # Rotation models moved to resource_planning_position.
        return
    periods = {
        key: env.ref("resource_planning." + xmlid, raise_if_not_found=False)
        for key, xmlid in PERIODS.items()
    }
    for xmlid, rows in PATTERNS.items():
        rotation = env.ref("resource_planning." + xmlid, raise_if_not_found=False)
        if not rotation or rotation.crew_ids:
            continue
        rotation.write(
            {
                "cycle_days": max(len(pattern) for pattern in rows.values()),
                "crew_ids": [
                    fields.Command.create(
                        {
                            "code": code,
                            "sequence": seq * 10,
                            "cell_ids": [
                                fields.Command.create(
                                    {
                                        "day": day + 1,
                                        "period_id": periods[period_key].id,
                                    }
                                )
                                for day, period_key in enumerate(pattern)
                                if periods[period_key]
                            ],
                        }
                    )
                    for seq, (code, pattern) in enumerate(rows.items(), 1)
                ],
            }
        )
