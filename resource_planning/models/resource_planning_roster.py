# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from collections import defaultdict
from datetime import timedelta

from odoo import fields, models


class ResourcePlanningRoster(models.AbstractModel):
    """Planning grid computation engine.

    Buckets dated planning records — assignments — into a row x day
    grid of per-cell recordsets and aggregates. Views (roster
    matrices), coverage KPIs and payroll calculations share this
    engine instead of reimplementing the day bucketing. The demand
    addon adds requirement coverage on top.
    """

    _name = "resource.planning.roster"
    _description = "Planning grid computation engine"

    def _roster_grid(self, records, row_field, date_field, date_from, days):
        """{crew_id: {date: recordset}} for the window.

        Each record lands on its ``row_field`` row and the local day
        of its ``date_field`` datetime.
        """
        grid = {}
        date_to = date_from + timedelta(days=days)
        for record in records:
            day = fields.Datetime.context_timestamp(record, record[date_field]).date()
            if not date_from <= day < date_to:
                continue
            row = grid.setdefault(record[row_field].id, defaultdict(record.browse))
            row[day] |= record
        return grid

    def _roster_cells(self, records, row_field, date_field, date_from, days):
        """{crew_id: {date: {"records", "hours"}}} — the grid plus
        per-cell aggregates for KPIs and payroll."""
        grid = self._roster_grid(records, row_field, date_field, date_from, days)
        return {
            crew_id: {
                day: {
                    "records": cell,
                    "hours": sum(
                        (rec.end_datetime - rec.start_datetime).total_seconds() / 3600
                        for rec in cell
                    ),
                }
                for day, cell in cells.items()
            }
            for crew_id, cells in grid.items()
        }

    def _split_on_leave(self, assignments):
        """(available, on_leave) split over `resource.calendar.leaves`.

        An assignment only covers demand while its resource is
        available: a leave overlapping the assignment's interval —
        the resource's own or a global one on its calendar — takes
        it out of coverage.
        """
        Assignment = self.env["resource.planning.assignment"]
        available, on_leave = Assignment.browse(), Assignment.browse()
        if not assignments:
            return available, on_leave
        leaves = self.env["resource.calendar.leaves"].search(
            [
                (
                    "resource_id",
                    "in",
                    assignments.resource_id.ids + [False],
                ),
                ("date_from", "<", max(assignments.mapped("end_datetime"))),
                ("date_to", ">", min(assignments.mapped("start_datetime"))),
            ]
        )
        for assignment in assignments:
            if any(
                leave.date_from < assignment.end_datetime
                and leave.date_to > assignment.start_datetime
                and leave.resource_id in (assignment.resource_id, False)
                and (
                    not leave.calendar_id
                    or leave.calendar_id == assignment.resource_id.calendar_id
                )
                for leave in leaves
            ):
                on_leave |= assignment
            else:
                available |= assignment
        return available, on_leave
