# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.intervals import Intervals
from odoo.tools.misc import format_datetime

from .resource_reservation_stage import RESERVATION_STATES
from .resource_reservation_type import _intervals_cover

# States that occupy their resources and keep a calendar event.
CONSUMING_STATES = [
    "scheduled",
    "in_progress",
    "done",
    "no_show",
]


class ResourceReservation(models.Model):
    _name = "resource.reservation"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _description = "Resource Reservation"
    _order = "start desc, id desc"

    active = fields.Boolean(default=True)
    name = fields.Char(
        index=True,
        help="Leave empty for an automatic name.",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        required=True,
        index=True,
        tracking=True,
    )
    type_id = fields.Many2one(
        comodel_name="resource.reservation.type",
        string="Type",
        required=True,
        index=True,
        tracking=True,
    )
    category_id = fields.Many2one(related="type_id.category_id", store=True, index=True)
    flow = fields.Selection(related="type_id.flow", store=True)
    stage_id = fields.Many2one(
        comodel_name="resource.reservation.stage",
        string="Stage",
        tracking=True,
        index=True,
        ondelete="restrict",
        domain="[('location_id', '=', location_id)]",
        group_expand="_read_group_stage_ids",
    )
    state = fields.Selection(
        selection=RESERVATION_STATES,
        default="requested",
        required=True,
        index=True,
        tracking=True,
        help="Fixed state, the anchor for automation and reporting. "
        "The kanban stage maps onto it.",
    )
    start = fields.Datetime(tracking=True, index=True, copy=False)
    duration = fields.Float(
        tracking=True,
        help="Reserved duration in hours (defaults to the type's).",
    )
    stop = fields.Datetime(compute="_compute_stop", store=True, index=True, copy=False)
    guests = fields.Integer(
        default=1,
        help="Party size; drives unit consumption on pool resources.",
    )
    location_id = fields.Many2one(
        comodel_name="res.partner",
        string="Location",
        tracking=True,
        index=True,
        domain="[('is_resource_location', '=', True)]",
        help="Where the reservation happens. Its timezone is the "
        "timezone of truth for display and reminders.",
    )
    videocall_location = fields.Char(string="Meeting URL")
    line_ids = fields.One2many(
        comodel_name="resource.reservation.line",
        inverse_name="reservation_id",
        string="Resources",
        copy=True,
    )
    hold_expiration = fields.Datetime(
        copy=False,
        help="Until this time the draft holds its slot. Expired drafts "
        "are released by the hold cleanup cron.",
    )
    is_hold = fields.Boolean(compute="_compute_is_hold")
    meeting_id = fields.Many2one(
        comodel_name="calendar.event",
        string="Calendar Event",
        copy=False,
        index=True,
        ondelete="set null",
        help="Synced projection of this reservation.",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Organizer",
        default=lambda self: self.env.user,
        tracking=True,
        help="Who organizes this reservation; the calendar event organizer.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
        index=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue")
    is_modifiable = fields.Boolean(compute="_compute_is_modifiable")

    _unique_meeting = models.Constraint(
        "UNIQUE(meeting_id)", "Only one event per reservation."
    )

    # ----------------------------------------------------------
    # Computations and defaults
    # ----------------------------------------------------------

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Show all stages of the relevant categories in kanban."""
        locations = self.search(domain).mapped("location_id")
        if locations:
            return self.env["resource.reservation.stage"].search(
                [("location_id", "in", locations.ids)]
            )
        return stages

    @api.depends("start", "duration")
    def _compute_stop(self):
        for reservation in self:
            if reservation.start and reservation.duration:
                reservation.stop = reservation.start + timedelta(
                    hours=reservation.duration
                )
            else:
                reservation.stop = False

    @api.depends("partner_id", "type_id", "start", "name")
    def _compute_display_name(self):
        result = super()._compute_display_name()
        for reservation in self:
            if reservation.name:
                continue
            parts = [
                reservation.partner_id.display_name or "",
                reservation.type_id.display_name or "",
            ]
            if reservation.start:
                parts.append(
                    format_datetime(
                        self.env,
                        reservation.start,
                        tz=reservation._get_tz(),
                        dt_format="short",
                    )
                )
            reservation.display_name = " — ".join(p for p in parts if p) or self.env._(
                "New"
            )
        return result

    @api.depends("start")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for reservation in self:
            if not reservation.start:
                reservation.is_overdue = False
                continue
            deadline = reservation.start - timedelta(
                hours=reservation.type_id.modifications_deadline
            )
            reservation.is_overdue = now > deadline

    @api.depends("is_overdue")
    @api.depends_context("uid", "using_portal")
    def _compute_is_modifiable(self):
        self.is_modifiable = True
        is_manager = not self.env.context.get(
            "using_portal"
        ) and self.env.user.has_group("resource_reservation.group_manager")
        if not is_manager:
            self.filtered("is_overdue").is_modifiable = False

    def _get_tz(self):
        """Timezone of truth: the reservation location's timezone."""
        self.ensure_one()
        return (
            self.location_id.tz
            or self.type_id.reservation_calendar_id.tz
            or self.env.user.tz
            or "UTC"
        )

    def _compute_access_url(self):
        result = super()._compute_access_url()
        for reservation in self:
            reservation.access_url = f"/reservation/{reservation.id}"
        return result

    @api.model
    def _mail_get_partner_fields(self, introspect_fields=False):
        return ["partner_id"]

    @api.onchange("type_id")
    def _onchange_type_id(self):
        """Reset type-dependent fields when the type changes."""
        for reservation in self:
            type_ = reservation.type_id
            reservation.duration = type_.duration
            reservation.videocall_location = type_.videocall_location
            if len(type_.location_ids) == 1:
                reservation.location_id = type_.location_ids
            elif reservation.location_id not in type_.location_ids:
                reservation.location_id = False
            reservation.stage_id = reservation.location_id._get_reservation_stage(
                "requested"
            )
            reservation.state = "requested"
            reservation.line_ids = [
                fields.Command.clear(),
                *(
                    fields.Command.create(
                        {
                            "type_leg_id": leg.id,
                            "role_id": leg.role_id.id,
                            "quantity": leg.quantity,
                            "sequence": leg.sequence,
                        }
                    )
                    for leg in type_.leg_ids
                ),
            ]

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def _get_consuming_states(self):
        return CONSUMING_STATES

    @api.depends("state", "hold_expiration")
    def _compute_is_hold(self):
        now = fields.Datetime.now()
        for reservation in self:
            reservation.is_hold = (
                reservation.state == "draft"
                and reservation.hold_expiration
                and reservation.hold_expiration > now
            )

    def action_extend_hold(self):
        """'I need more time': restart the hold countdown."""
        for reservation in self:
            if reservation.is_hold and reservation.type_id.hold_duration:
                reservation.hold_expiration = fields.Datetime.now() + timedelta(
                    minutes=reservation.type_id.hold_duration
                )
        return True

    def _set_state(self, state):
        """Move to a fixed state; sync stage when the category maps it."""
        for reservation in self:
            vals = {"state": state}
            stage = reservation.location_id._get_reservation_stage(state)
            if stage:
                vals["stage_id"] = stage.id
            reservation.write(vals)

    def _prepare_lines_for_scheduling(self):
        """Pool lines consume at least `guests` units."""
        for reservation in self:
            for line in reservation.line_ids:
                if (
                    line.resource_id
                    and line.resource_id.quantity > 1
                    and line.quantity < reservation.guests
                ):
                    line.quantity = reservation.guests

    def action_schedule(self):
        """Schedule at the stored start: assign legs, create event."""
        for reservation in self:
            if not reservation.start:
                raise ValidationError(
                    self.env._(
                        "Pick a slot before scheduling %s",
                        reservation.display_name,
                    )
                )
            reservation._check_availability()
            reservation._assign_missing_resources()
            reservation._prepare_lines_for_scheduling()
            reservation._set_state("scheduled")
        self.write({"hold_expiration": False})
        self._sync_meeting()

    def action_confirm(self):
        """Advance to the next pipeline stage (e.g. Scheduled → Confirmed).

        Confirmation is pipeline granularity, not a system state: a
        location that wants it maps a stage to `scheduled`.
        """
        for reservation in self:
            next_stage = reservation.location_id.stage_ids.filtered(
                lambda s, seq=reservation.stage_id.sequence or 0: s.sequence > seq
            )[:1]
            if next_stage:
                reservation.stage_id = next_stage

    def action_attend(self):
        """Check-in: the customer arrived (IN flow)."""
        self._set_state("in_progress")

    def action_no_show(self):
        self._set_state("no_show")

    def action_pick_up(self):
        """Pick-up: the resource left with the customer (OUT flow)."""
        self._set_state("in_progress")

    def action_return(self):
        """Done: appointment completed or item returned."""
        self._set_state("done")

    def action_unschedule(self):
        """Back to requested: clear slot and legs, drop the event."""
        self.write({"start": False})
        self.line_ids.write({"resource_id": False})
        self.mapped("meeting_id").unlink()
        self._set_state("requested")

    def action_cancel(self):
        """Cancel: remove the event projection and archive."""
        self.mapped("meeting_id").unlink()
        self.write(
            {
                "active": False,
                "state": "cancelled",
                "access_token": False,
                "hold_expiration": False,
            }
        )

    def action_assign(self):
        """Auto-assign resources for legs left empty."""
        self._check_availability()
        self._assign_missing_resources()

    def action_open_portal(self):
        return {
            "target": "self",
            "type": "ir.actions.act_url",
            "url": self.get_portal_url(),
        }

    def action_open_meeting(self):
        self.ensure_one()
        if self.meeting_id:
            return self.meeting_id.get_formview_action()

    # ----------------------------------------------------------
    # Availability and assignment
    # ----------------------------------------------------------

    def _get_available_slots(self, start_dt, end_dt):
        """Slots for this reservation's type/location, self excluded."""
        self.ensure_one()
        return self.type_id._get_available_slots(
            start_dt,
            end_dt,
            location_id=self.location_id.id or None,
            guests=self.guests or 1,
            exclude_reservation=self,
        )

    def _check_availability(self):
        """The span must be free for every leg (assigned or not)."""
        for reservation in self:
            if not reservation.start or not reservation.stop:
                continue
            if reservation.stop < fields.Datetime.now():
                continue
            start_dt = fields.Datetime.context_timestamp(reservation, reservation.start)
            stop_dt = fields.Datetime.context_timestamp(reservation, reservation.stop)
            unfitting = []
            for line in reservation.line_ids:
                free_map = reservation.type_id._get_leg_free_map(
                    line.type_leg_id or reservation._get_default_leg(line),
                    start_dt,
                    stop_dt,
                    location_id=reservation.location_id.id or None,
                    guests=reservation.guests or 1,
                    exclude_reservation=reservation,
                )
                if line.resource_id:
                    fits = _intervals_cover(
                        free_map.get(line.resource_id.id, Intervals([])),
                        start_dt,
                        stop_dt,
                    )
                else:
                    fits = any(
                        _intervals_cover(intervals, start_dt, stop_dt)
                        for intervals in free_map.values()
                    )
                if not fits:
                    unfitting.append(line)
            if unfitting:
                raise ValidationError(
                    self.env._(
                        "Cannot schedule %(name)s: no available resource for "
                        "role(s) %(functions)s on the chosen slot.",
                        name=reservation.display_name,
                        functions=", ".join(
                            line.role_id.display_name for line in unfitting
                        ),
                    )
                )

    def _get_default_leg(self, line):
        """Synthetic leg for lines without a type leg link."""
        return self.env["resource.reservation.type.leg"].new(
            {
                "role_id": line.role_id.id,
                "quantity": line.quantity or 1,
            }
        )

    def _assign_missing_resources(self):
        """Fill unassigned legs per the type's assignment policy."""
        for reservation in self:
            start_dt = fields.Datetime.context_timestamp(reservation, reservation.start)
            stop_dt = fields.Datetime.context_timestamp(reservation, reservation.stop)
            for line in reservation.line_ids.filtered(
                lambda line: not line.resource_id
            ):
                line.resource_id = reservation.type_id._assign_leg_resource(
                    line.type_leg_id or reservation._get_default_leg(line),
                    start_dt,
                    stop_dt,
                    location_id=reservation.location_id.id or None,
                    guests=reservation.guests or 1,
                )
                if not line.resource_id:
                    raise ValidationError(
                        self.env._(
                            "No resource available for role %(function)s on %(name)s.",
                            function=line.role_id.display_name,
                            name=reservation.display_name,
                        )
                    )

    @api.constrains("line_ids", "start", "state", "location_id")
    def _check_scheduling(self):
        """Scheduled reservations must have no conflicts."""
        scheduled = self.filtered(lambda r: r.start and r.state in CONSUMING_STATES)
        scheduled._check_availability()

    # ----------------------------------------------------------
    # calendar.event sync (projection only)
    # ----------------------------------------------------------

    def _prepare_meeting_vals(self):
        self.ensure_one()
        resource_partners = self.line_ids.resource_id.filtered(
            lambda res: res.resource_type == "user"
        ).mapped("user_id.partner_id")
        vals = {
            "name": self.name
            or " — ".join(
                p
                for p in [self.partner_id.display_name, self.type_id.display_name]
                if p
            ),
            "start": self.start,
            "stop": self.stop,
            "duration": self.duration,
            "location": self.location_id.display_name or False,
            "videocall_location": self.videocall_location,
            "partner_ids": [
                fields.Command.link(partner.id) for partner in resource_partners
            ],
            "user_id": self.user_id.id,
            "show_as": "busy",
            "res_model_id": False,
            "res_id": False,
            "reservation_ids": [fields.Command.set(self.ids)],
        }
        if self.type_id.requester_advice:
            vals["description"] = self.type_id.requester_advice
        return vals

    @api.model
    def _cron_expire_holds(self):
        """Release draft reservations whose hold ran out."""
        expired = self.search(
            [
                ("state", "=", "draft"),
                ("hold_expiration", "<", fields.Datetime.now()),
            ]
        )
        expired.action_cancel()
        return True

    def _sync_meeting(self):
        """Lazy create/update/destroy of the linked calendar.event."""
        _self = self.with_context(syncing_reservation_ids=self.ids)
        _self -= self.browse(self.env.context.get("syncing_reservation_ids") or [])
        to_create = []
        for reservation in _self:
            consuming = (
                reservation.start
                and reservation.state in reservation._get_consuming_states()
            )
            if consuming:
                vals = reservation._prepare_meeting_vals()
                if reservation.meeting_id:
                    reservation.meeting_id.with_context(from_ui=True).write(vals)
                else:
                    # event_tz is a "recurrent field": only set on create.
                    vals["event_tz"] = reservation._get_tz()
                    to_create.append(vals)
            elif reservation.meeting_id:
                reservation.meeting_id.unlink()
        if to_create:
            _self.env["calendar.event"].create(to_create)

    @api.model_create_multi
    def create(self, vals_list):
        # Onchange defaults are UI-only; repeat them here for code callers.
        for vals in vals_list:
            type_ = self.env["resource.reservation.type"].browse(vals.get("type_id"))
            if type_:
                vals.setdefault("duration", type_.duration)
                if not vals.get("location_id") and len(type_.location_ids) == 1:
                    vals["location_id"] = type_.location_ids.id
                vals.setdefault("videocall_location", type_.videocall_location)
        reservations = super().create(vals_list)
        for reservation in reservations:
            if reservation.type_id and not reservation.line_ids:
                reservation.line_ids = [
                    fields.Command.create(
                        {
                            "type_leg_id": leg.id,
                            "role_id": leg.role_id.id,
                            "quantity": leg.quantity,
                            "sequence": leg.sequence,
                        }
                    )
                    for leg in reservation.type_id.leg_ids
                ]
            if not reservation.stage_id:
                reservation.stage_id = reservation.location_id._get_reservation_stage(
                    reservation.state or "requested"
                )
        reservations._sync_meeting()
        return reservations

    def write(self, vals):
        # Moving the kanban stage syncs the fixed state.
        if "stage_id" in vals and "state" not in vals:
            stage = self.env["resource.reservation.stage"].browse(vals["stage_id"])
            if stage:
                vals["state"] = stage.state
        result = super().write(vals)
        if any(key in vals for key in ("start", "stop", "duration", "state")):
            self._sync_meeting()
        return result

    def unlink(self):
        self.mapped("meeting_id").unlink()
        return super().unlink()
