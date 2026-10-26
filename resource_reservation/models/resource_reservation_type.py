# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from collections import defaultdict
from datetime import timedelta
from random import random

from odoo import api, fields, models
from odoo.tools.intervals import Intervals


def _merge_intervals(intervals):
    """Merge intervals where a stop equals the next start."""
    items = [list(item) for item in intervals._items]
    for i in range(len(items) - 1, 0, -1):
        if items[i][0] == items[i - 1][1]:
            items[i - 1][1] = items[i][1]
            del items[i]
    return Intervals([tuple(item) for item in items])


def _intervals_cover(intervals, start, stop):
    """``[start, stop)`` is covered by the union of `intervals`.

    Contiguous intervals chain (e.g. continuous 0-24 attendances let a
    multi-day stay fit); real gaps still break coverage. Micro-gaps of
    a second or less count as contiguous — `hour_to=24` ends at
    23:59:59.999999.
    """
    cursor = start
    tolerance = timedelta(seconds=1)
    for s, e, _items in sorted(intervals._items, key=lambda i: i[0]):
        if s > cursor + tolerance:
            break
        if e > cursor:
            cursor = e
            if cursor >= stop:
                return True
    return cursor >= stop


class ResourceReservationType(models.Model):
    _name = "resource.reservation.type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Reservation Type"
    _order = "sequence, name"

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, translate=True, index="trigram")
    sequence = fields.Integer(default=10)
    color = fields.Integer()
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name="resource.reservation.category",
        required=True,
        index=True,
        ondelete="restrict",
        help="Grouping category; also owns the stage pipeline.",
    )
    flow = fields.Selection(
        selection=[("in", "IN — customer on-site"), ("out", "OUT — resource leaves")],
        required=True,
        default="in",
        help="IN: the customer comes to the location (appointments, "
        "stays). OUT: the customer takes the resource away (rentals).",
    )
    duration = fields.Float(
        required=True,
        default=1.0,
        help="Reservation duration in hours. May span several days "
        "(e.g. 20h for one hotel night).",
    )
    hold_duration = fields.Integer(
        string="Slot hold (min)",
        default=15,
        help="Minutes a picked slot is held during checkout. 0 disables holds.",
    )
    slot_grid_interval = fields.Float(
        string="Slot grid interval",
        default=0,
        help="Start-time grid granularity in hours, e.g. 0.25 for "
        ":00/:15/:30/:45 starts. Empty: uses slot duration.",
    )
    slot_duration = fields.Float(
        required=True,
        default=0.5,
        help="Granularity of offered start times, in hours. "
        "Independent of the reservation duration.",
    )
    reservation_calendar_id = fields.Many2one(
        comodel_name="resource.calendar",
        string="Availability Schedule",
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda self: self.env.company.resource_calendar_id,
        help="Reservations may only start inside this schedule.",
    )
    booking_min_notice = fields.Float(
        string="Min notice (hours)",
        default=0.0,
        help="Slots must start at least this many hours from now.",
    )
    booking_max_horizon = fields.Float(
        string="Max horizon (days)",
        default=0.0,
        help="Slots may not start further than this many days away. 0 = no limit.",
    )
    modifications_deadline = fields.Float(
        required=True,
        default=24.0,
        help="Hours before start after which only managers may reschedule or cancel.",
    )
    buffer_before = fields.Float(
        string="Buffer before (hours)",
        default=0.0,
        help="Blocking time reserved before each booking (setup, cleaning).",
    )
    buffer_after = fields.Float(
        string="Buffer after (hours)",
        default=0.0,
        help="Blocking time reserved after each booking (cleanup, inspection).",
    )
    location_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Locations",
        domain="[('is_resource_location', '=', True)]",
        help="Locations where this type is offered. Empty: available at any location.",
    )
    videocall_location = fields.Char(
        string="Videocall URL",
        help="If set, reservations may be held remotely at this URL "
        "instead of a physical location.",
    )
    leg_ids = fields.One2many(
        comodel_name="resource.reservation.type.leg",
        inverse_name="type_id",
        string="Required Functions",
        copy=True,
        help="Each leg is a role slot filled by a matching "
        "resource when the booking is scheduled.",
    )
    assignment = fields.Selection(
        selection=[
            ("sorted", "Sorted: pick the first free candidate"),
            ("random", "Random"),
            ("least_used", "Least used in the window"),
        ],
        required=True,
        default="sorted",
        help="How to fill role legs left unassigned.",
    )
    allow_resource_choice = fields.Boolean(
        string="Customer chooses resource",
        default=True,
        help="Let the customer pick a specific resource instead of auto-assignment.",
    )
    allow_no_preference = fields.Boolean(
        string="Allow 'no preference'",
        default=True,
        help="Offer auto-assignment ('no preference') when the customer "
        "may pick a resource.",
    )
    requester_advice = fields.Text(
        translate=True,
        help="Shown in invitation pages and added to the calendar event's description.",
    )
    reservation_ids = fields.One2many(
        comodel_name="resource.reservation",
        inverse_name="type_id",
        string="Reservations",
    )
    reservation_count = fields.Integer(compute="_compute_reservation_count")

    _check_duration = models.Constraint(
        "CHECK(duration > 0)", "Duration must be positive."
    )
    _check_slot_duration = models.Constraint(
        "CHECK(slot_duration > 0)", "Slot duration must be positive."
    )
    _check_slot_grid_interval = models.Constraint(
        "CHECK(slot_grid_interval >= 0)",
        "Slot grid interval must not be negative.",
    )

    @api.depends("reservation_ids")
    def _compute_reservation_count(self):
        counts = dict(
            self.env["resource.reservation"]._read_group(
                [("type_id", "in", self.ids)], ["type_id"], ["__count"]
            )
        )
        for type_ in self:
            type_.reservation_count = counts.get(type_, 0)

    # ----------------------------------------------------------
    # Availability engine
    # ----------------------------------------------------------

    def _get_leg_candidates(self, leg):
        """Bookable resources carrying the leg's role."""
        return self.env["resource.resource"].search(
            [
                ("bookable", "=", True),
                ("role_ids", "in", leg.role_id.ids),
            ]
        )

    def _get_leg_free_map(
        self,
        leg,
        start_dt,
        end_dt,
        location_id=None,
        guests=1,
        exclude_reservation=None,
    ):
        """Free intervals per candidate resource for one leg.

        Returns ``{resource_id: Intervals}``. The map intersects the
        type's schedule, the resource's valid work intervals (calendar
        + leaves), the resource's presence at ``location_id``, and
        subtracts busy spans where the resource's pool capacity would
        be exceeded.
        """
        self.ensure_one()
        candidates = self._get_leg_candidates(leg)
        free = {res.id: Intervals([]) for res in candidates}
        if not candidates:
            return free
        work_intervals, _unused = candidates._get_valid_work_intervals(start_dt, end_dt)
        type_intervals = self.reservation_calendar_id._work_intervals_batch(
            start_dt, end_dt
        )[False]
        location_map = candidates.get_locations_on_period(start_dt, end_dt)
        busy = self.env["resource.reservation.line"]._get_busy_intervals(
            candidates, start_dt, end_dt, exclude_reservation=exclude_reservation
        )
        buffer_before = timedelta(hours=self.buffer_before)
        buffer_after = timedelta(hours=self.buffer_after)
        for res in candidates:
            need = leg.quantity
            if res.quantity > 1:
                need = max(need, guests)
            intervals = work_intervals[res.id] & type_intervals
            presence = location_map[res.id]
            if presence and location_id:
                intervals = intervals & presence.get(location_id, Intervals([]))
            busy_expanded = Intervals(
                (s - buffer_before, e + buffer_after, lines)
                for s, e, lines in busy.get(res.id, Intervals([]))
            )
            blocked = Intervals(
                (s, e, lines)
                for s, e, lines in busy_expanded
                if sum(lines.mapped("quantity")) + need > res.quantity
            )
            free[res.id] = intervals - blocked
        return free

    def _get_available_slots(
        self, start_dt, end_dt, location_id=None, guests=1, exclude_reservation=None
    ):
        """Offerable slot starts, grouped by local date.

        Returns ``{date: [datetime, ...]}`` in the type calendar's
        timezone context (callers should set `tz` in context).
        """
        self.ensure_one()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        if not start_dt.tzinfo:
            start_dt = fields.Datetime.context_timestamp(self, start_dt)
        if not end_dt.tzinfo:
            end_dt = fields.Datetime.context_timestamp(self, end_dt)
        start_dt = max(start_dt, now + timedelta(hours=self.booking_min_notice))
        if self.booking_max_horizon:
            end_dt = min(end_dt, now + timedelta(days=self.booking_max_horizon))
        if start_dt >= end_dt:
            return {}
        legs = self.leg_ids
        leg_maps = [
            (
                leg,
                self._get_leg_free_map(
                    leg, start_dt, end_dt, location_id, guests, exclude_reservation
                ),
            )
            for leg in legs
        ]
        type_intervals = _merge_intervals(
            self.reservation_calendar_id._work_intervals_batch(start_dt, end_dt)[False]
        )
        duration = timedelta(hours=self.duration)
        step = timedelta(hours=self.slot_grid_interval or self.slot_duration)
        result = defaultdict(list)
        for s, e, _items in type_intervals._items:
            start = s
            while start + duration <= e:
                if start >= start_dt and self._span_fits_all_legs(
                    start, start + duration, leg_maps
                ):
                    result[start.date()].append(start)
                start += step
        return dict(result)

    def _span_fits_all_legs(self, start, stop, leg_maps):
        """Every leg has at least one candidate covering [start, stop)."""
        for _leg, free_map in leg_maps:
            if not any(
                _intervals_cover(intervals, start, stop)
                for intervals in free_map.values()
            ):
                return False
        return True

    def _is_span_free(
        self, start_dt, end_dt, location_id=None, guests=1, exclude_reservation=None
    ):
        """A reservation of this type can occupy [start_dt, end_dt)."""
        self.ensure_one()
        for leg in self.leg_ids:
            free_map = self._get_leg_free_map(
                leg, start_dt, end_dt, location_id, guests, exclude_reservation
            )
            if not any(
                _intervals_cover(intervals, start_dt, end_dt)
                for intervals in free_map.values()
            ):
                return False
        return True

    # ----------------------------------------------------------
    # Assignment
    # ----------------------------------------------------------

    def _assign_leg_resource(self, leg, start_dt, end_dt, location_id=None, guests=1):
        """Pick a candidate resource for the leg per `assignment`."""
        self.ensure_one()
        free_map = self._get_leg_free_map(leg, start_dt, end_dt, location_id, guests)
        candidates = self.env["resource.resource"].browse(
            res_id
            for res_id, intervals in free_map.items()
            if _intervals_cover(intervals, start_dt, end_dt)
        )
        if not candidates:
            return self.env["resource.resource"]
        if self.assignment == "random":
            candidates = candidates.sorted(lambda _r: random())
        elif self.assignment == "least_used":
            counts = self._get_reservation_counts(candidates, start_dt, end_dt)
            candidates = candidates.sorted(
                lambda r: (counts.get(r.id, 0), r.sequence, r.id)
            )
        else:
            candidates = candidates.sorted(lambda r: (r.sequence, r.id))
        return candidates[:1]

    def _get_reservation_counts(self, resources, start_dt, end_dt):
        """Reservation line counts per resource in the window."""
        groups = self.env["resource.reservation.line"]._read_group(
            [
                ("resource_id", "in", resources.ids),
                ("reservation_id.active", "=", True),
                ("reservation_id.state", "!=", "cancelled"),
                ("reservation_id.start", "<", end_dt),
                ("reservation_id.stop", ">", start_dt),
            ],
            ["resource_id"],
            ["__count"],
        )
        return {resource.id: count for resource, count in groups}

    def action_open_reservations(self):
        return {
            "domain": [("type_id", "=", self.id)],
            "context": {"default_type_id": self.id},
            "name": self.env._("Reservations"),
            "res_model": "resource.reservation",
            "type": "ir.actions.act_window",
            "view_mode": "calendar,list,kanban,form",
        }
