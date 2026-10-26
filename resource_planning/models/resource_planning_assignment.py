# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from collections import defaultdict
from datetime import timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import ValidationError

ASSIGNMENT_STATES = [
    ("draft", "Draft"),
    ("planned", "Planned"),
    ("published", "Published"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

# States that consume the resource's time: they count for coverage and
# busy-interval checks.
CONSUMING_STATES = ["planned", "published", "completed"]

# States where overlap with another consuming assignment is a hard
# conflict. Drafts stay tentative; completed records are history and are
# never re-validated.
BLOCKING_STATES = ["planned", "published"]


def _intervals_cover(intervals, start, stop):
    """Whether the union of `intervals` covers the ``[start, stop)`` span."""
    cursor = start
    for s, e, _items in sorted(intervals._items, key=lambda i: i[0]):
        if s > cursor:
            break
        if e > cursor:
            cursor = e
            if cursor >= stop:
                return True
    return cursor >= stop


class ResourcePlanningAssignment(models.Model):
    """Allocation of a generic resource to a time interval.

    Ad hoc work needs no demand: the demand addon adds the optional
    links to a service and a requirement.
    """

    _name = "resource.planning.assignment"
    _description = "Assignment"
    _order = "start_datetime, id"

    active = fields.Boolean(default=True)
    name = fields.Char(help="Leave empty for an automatic name.")
    resource_id = fields.Many2one(
        comodel_name="resource.resource",
        string="Resource",
        required=True,
        index=True,
    )
    role_id = fields.Many2one(
        comodel_name="resource.role",
        string="Role",
        index=True,
        help="The role fulfilled, when relevant for validation and "
        "reporting. Defaults to the requirement's role.",
    )
    start_datetime = fields.Datetime(required=True, index=True)
    end_datetime = fields.Datetime(required=True)
    state = fields.Selection(
        selection=ASSIGNMENT_STATES,
        default="draft",
        required=True,
        index=True,
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        index=True,
    )
    color = fields.Integer()
    conflict_ids = fields.Many2many(
        comodel_name="resource.planning.assignment",
        relation="resource_assignment_conflict_rel",
        column1="assignment_id",
        column2="conflict_id",
        string="Conflicting Assignments",
        compute="_compute_conflicts",
        help="Other consuming assignments overlapping this one.",
    )
    has_conflicts = fields.Boolean(compute="_compute_conflicts")
    warning_message = fields.Text(
        compute="_compute_warnings",
        help="Eligibility warnings: non-blocking issues the planner may "
        "choose to override.",
    )

    # ----------------------------------------------------------
    # Computations and defaults
    # ----------------------------------------------------------

    @api.depends("name", "resource_id", "start_datetime")
    def _compute_display_name(self):
        result = super()._compute_display_name()
        for assignment in self:
            if assignment.name:
                continue
            parts = [assignment.resource_id.display_name or ""]
            if assignment.start_datetime:
                parts.append(fields.Datetime.to_string(assignment.start_datetime)[:16])
            assignment.display_name = " — ".join(p for p in parts if p) or self.env._(
                "New"
            )
        return result

    @api.depends("resource_id", "start_datetime", "end_datetime", "state")
    def _compute_conflicts(self):
        for assignment in self:
            assignment.conflict_ids = assignment._find_conflicts()
            assignment.has_conflicts = bool(assignment.conflict_ids)

    @api.depends(
        "resource_id",
        "resource_id.role_ids",
        "role_id",
        "start_datetime",
        "end_datetime",
    )
    def _compute_warnings(self):
        for assignment in self:
            issues = assignment._get_warning_issues()
            assignment.warning_message = "\n".join(issues) if issues else False

    # ----------------------------------------------------------
    # Conflicts, availability and eligibility
    # ----------------------------------------------------------

    def _get_consuming_states(self):
        """States that occupy the resource. Extension point."""
        return CONSUMING_STATES

    def _get_blocking_states(self):
        """States where overlaps are hard conflicts. Extension point."""
        return BLOCKING_STATES

    def _find_conflicts(self):
        """Other consuming assignments of the same resource, overlapping.

        Intervals are half-open ``[start, end)``: adjacent assignments
        ending and starting at the same instant do not conflict.
        """
        self.ensure_one()
        origin = self._origin or self
        if (
            not isinstance(origin.id, int)
            or not self.resource_id
            or not self.start_datetime
            or not self.end_datetime
        ):
            return self.env[self._name]
        return self.search(
            [
                ("id", "!=", origin.id),
                ("resource_id", "=", self.resource_id.id),
                ("state", "in", self._get_consuming_states()),
                ("start_datetime", "<", self.end_datetime),
                ("end_datetime", ">", self.start_datetime),
            ]
        )

    def _get_blocking_issues(self):
        """Hard problems preventing a plan or publish. Extension point."""
        self.ensure_one()
        issues = []
        if not self.resource_id.active:
            issues.append(
                self.env._("%(resource)s is archived.", resource=self.resource_id.name)
            )
        conflicts = self._find_conflicts()
        for other in conflicts:
            issues.append(
                self.env._(
                    "%(resource)s is already assigned to %(other)s.",
                    resource=self.resource_id.name,
                    other=other.display_name,
                )
            )
        return issues

    def _get_expected_role(self):
        """The role the assignment should fulfil. Extension point —
        the demand addon falls back to the requirement's role."""
        return self.role_id

    def _get_warning_issues(self):
        """Non-blocking eligibility issues. Extension point.

        The HR addon adds employee leave and HR eligibility here.
        """
        self.ensure_one()
        issues = []
        resource = self.resource_id
        role = self._get_expected_role()
        if role and resource.role_ids and role not in resource.role_ids:
            issues.append(
                self.env._(
                    "%(resource)s is not declared for the %(role)s role.",
                    resource=resource.name,
                    role=role.name,
                )
            )
        if resource.calendar_id and self.start_datetime and self.end_datetime:
            start = self.start_datetime.replace(tzinfo=timezone.utc)
            end = self.end_datetime.replace(tzinfo=timezone.utc)
            work = resource.calendar_id._work_intervals_batch(
                start, end, resources=resource
            )[resource.id]
            if not _intervals_cover(work, start, end):
                issues.append(
                    self.env._(
                        "%(resource)s is outside their working calendar.",
                        resource=resource.name,
                    )
                )
        return issues

    @api.constrains("resource_id", "start_datetime", "end_datetime", "state")
    def _check_conflicts(self):
        """Hard conflicts prevent planning or publishing, server-side."""
        for assignment in self:
            if assignment.state not in assignment._get_blocking_states():
                continue
            issues = assignment._get_blocking_issues()
            if issues:
                raise ValidationError("\n".join(issues))

    @api.constrains("start_datetime", "end_datetime")
    def _check_interval(self):
        for assignment in self:
            if (
                assignment.start_datetime
                and assignment.end_datetime
                and assignment.end_datetime <= assignment.start_datetime
            ):
                raise ValidationError(
                    self.env._("The end must be later than the start.")
                )

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def action_plan(self):
        self.write({"state": "planned"})

    def action_publish(self):
        self.write({"state": "published"})

    def action_complete(self):
        self.write({"state": "completed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_draft(self):
        self.write({"state": "draft"})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_published(self):
        published = self.filtered(lambda a: a.state == "published")
        if published:
            raise ValidationError(
                self.env._(
                    "Cannot delete published assignments. Cancel them first: %(names)s",
                    names=", ".join(published.mapped("display_name")),
                )
            )

    def _assignments_by_day(self, date_from, days=28):
        """Internal API: {resource_id: {date: assignments}}.

        Shared by roster views, coverage KPIs and payroll
        aggregations — the resource's assignments keyed by local day.
        """
        Assignment = self.env["resource.planning.assignment"]
        grid = {resource.id: defaultdict(Assignment.browse) for resource in self}
        if not self:
            return grid
        assignments = Assignment.search(
            [
                ("resource_id", "in", self.ids),
                ("start_datetime", ">=", date_from),
                ("start_datetime", "<", date_from + timedelta(days=days)),
                ("state", "in", ["planned", "published", "completed"]),
            ]
        )
        return self.env["resource.planning.roster"]._roster_grid(
            assignments, "resource_id", "start_datetime", date_from, days
        )
