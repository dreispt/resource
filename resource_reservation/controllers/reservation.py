# Copyright 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import calendar as pycal
from datetime import timezone

from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request, route

from odoo.addons.portal.controllers.portal import CustomerPortal


class ReservationPortal(CustomerPortal):
    def _get_reservation_sudo(self, reservation_id, access_token):
        """Token-checked access to the reservation."""
        return self._document_check_access(
            "resource.reservation", reservation_id, access_token
        )

    def _get_schedule_context(self, reservation, year=None, month=None):
        """Month grid data for the invitation scheduling page."""
        month_delta = relativedelta(months=1)
        now = fields.Datetime.context_timestamp(reservation, fields.Datetime.now())
        year = int(year) if year else now.year
        month = int(month) if month else now.month
        start = now.replace(
            year=year,
            month=month,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        slots = reservation._get_available_slots(
            start, start + month_delta + relativedelta(hours=reservation.duration or 1)
        )
        lang = request.env["res.lang"]._lang_get(
            request.env.lang or request.env.user.lang
        )
        weekday_names = dict(lang.fields_get(["week_start"])["week_start"]["selection"])
        cal = pycal.Calendar(int(lang.week_start) - 1)
        return {
            "calendar": cal,
            "month_delta": month_delta,
            "now": now,
            "slots": slots,
            "start": start,
            "weekday_headers": [weekday_names[str(i + 1)] for i in cal.iterweekdays()],
        }

    @route(
        ["/reservation/<int:reservation_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def reservation_page(
        self,
        reservation_id,
        access_token=None,
        year=None,
        month=None,
        date=None,
        error=None,
        **kw,
    ):
        """Invitation page: pick a slot, or review the scheduled one."""
        try:
            reservation = self._get_reservation_sudo(reservation_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        reservation = reservation.with_context(
            using_portal=True, tz=reservation._get_tz()
        )
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "reservation": reservation,
                "access_token": access_token,
                "error": error,
                "page_name": "reservation",
                "state_label": dict(
                    reservation._fields["state"]._description_selection(request.env)
                ).get(reservation.state),
            }
        )
        if reservation.state == "draft":
            values.update(self._get_schedule_context(reservation, year, month))
            values["selected_date"] = date
            if date:
                try:
                    selected = fields.Date.to_date(date)
                    values["day_slots"] = values["slots"].get(selected, [])
                except ValueError:
                    values["day_slots"] = []
        return request.render("resource_reservation.reservation_page", values)

    @route(
        ["/reservation/<int:reservation_id>/schedule"],
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def reservation_schedule(self, reservation_id, access_token=None, slot=None, **kw):
        """Confirm the chosen slot on a draft reservation."""
        try:
            reservation = self._get_reservation_sudo(reservation_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        reservation = reservation.with_context(using_portal=True)
        error = None
        try:
            start = isoparse(slot)
            if start.tzinfo is None:
                raise ValidationError(request.env._("Invalid slot."))
            reservation.sudo().write(
                {"start": start.astimezone(timezone.utc).replace(tzinfo=None)}
            )
            reservation.sudo().action_schedule()
        except (ValidationError, ValueError, TypeError) as exc:
            error = str(exc.args[0] if exc.args else exc)
        url = f"/reservation/{reservation.id}"
        if access_token:
            url += f"?access_token={access_token}"
            if error:
                url += f"&error={error}"
        return request.redirect(url)
