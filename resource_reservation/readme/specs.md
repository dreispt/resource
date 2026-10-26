# Resource Reservation app — analysis

**Status:** in progress — phase 1 core module under construction at
`~/work19/oca/resource/resource_reservation`.
**Date:** 2026-10-25
**Scope:** a new LGPL-3 Odoo app for resource reservations (bookings /
appointments). In a later phase it replaces the Enterprise `appointment` /
`website_appointment` modules and the `brb_*` customizations in
`~/work19/barberhood`.
**License target:** LGPL-3 (OCA `resource` repo; author Daniel Reis).
**Related:** `~/work19/barberhood/DESIGN.md` (existing suite to be superseded),
`~/work19/barberhood/docs/portal-appointments.md` and
`waitlist-online-signup.md` (portal + waitlist requirements),
`~/work19/oca/calendar/resource_booking` (closest OCA module, compared below),
`docs/RESOURCE_RESERVATION_PRIOR_ART.md` (Fresha/Treatwell competitor
analysis).

---

## 1. Context

- Odoo's own Appointments app (`appointment`, `website_appointment`) is
  **Enterprise-only (OEEL-1)**. Every barberhood `brb_*` module depends on it,
  so the whole booking stack currently requires an Enterprise subscription.
- The target app must be **LGPL-3** so it can live in OCA and be reused by
  Community deployments without license friction.
- The same core — "a customer reserves a resource (person, place, thing) for a
  time slot" — serves several verticals with different wrinkles. Designing for
  all of them up front avoids a barber-only model that needs surgery later.

## 2. Use cases

| Vertical | Bookable resource | Who books | Distinct requirements |
| --- | --- | --- | --- |
| Hair / barber shop | Staff member (barber) | Public visitor, front desk | Staff choice or "no preference", service products, price varies by staff seniority, check-in, POS/SO checkout, no-show tracking, reminders |
| Beauty salon | Staff member, possibly + room/chair | Public visitor, front desk | Same as barber; multi-service bookings in one visit; longer, variable durations; services may require staff **functions** (e.g. colorist); **segmented durations** — colorist leg occupied only on apply/finish segments, chair leg throughout, staff bookable mid-visit |
| Medical clinic | Doctor + room + equipment (combined) | Patient, receptionist | Combination booking (all resources must be free); **sequential legs** — nurse intake → doctor consult → nurse checkout, each leg occupying its own segment; privacy (patient data hidden from non-clinical staff), intake questions, stricter cancellation rules |
| Tennis court | Court (capacity 1), optionally + coach | Club member, public | Resource-only or resource+staff combination; coach as an **optional leg** — drops out if unavailable, keeps the court; simple self-service, possibly payment upfront |
| Vehicle service | Bay + mechanic | Phone/front desk | Segmented demand — mechanic leg on inspection/reassembly segments only, bay leg for the whole stay; unattended gaps while parts arrive or paint dries |
| Restaurant | Seat pool at the location | Public visitor | **Party size** (booking consumes N seats from the pool), seating turns (lunch/dinner windows), no staff choice |
| Hotel / accommodation | Room (multi-night stay) | Guest, reception | **IN flow but multi-day**: nights-based duration, fixed check-in/out hours, housekeeping buffer between stays |
| Equipment rental | Unit from a pool (bike, tool, car) | Public visitor, member | **OUT flow**: customer takes the resource off-site; interchangeable units, multi-day durations, pickup/return windows, deposit, return-condition check |

Cross-cutting: phone/walk-in bookings by staff, guest (no-login) booking,
cancellation and rescheduling by the customer, reminders (email/SMS),
time-zone correctness, multi-location operation (each site has its own
resource pool), in/out flows (customer comes in vs. takes the resource
out), and reporting on utilization/no-shows.

## 3. Capability inventory (what the app must do)

### Core / backend

- **Reservation types** — the "what is being booked": name, in/out flow,
  duration, required roles, availability schedule, booking window
  rules (min notice, max horizon), cancellation deadline, the locations
  where it is offered (incl. videocall), confirmation/cancel/reminder
  message templates.
- **Categories** — types are grouped in categories (the front-office
  discovery dimension).
- **Stage pipelines per location** — each *location* configures its own
  stage pipeline: ordered, renameable stage records (the
  `project.task.type` pattern). Opening a location shows one board
  across all its services. Every stage maps to a fixed `state` on the
  reservation, so automations and reporting key on a stable list while
  each site shapes its own board.
  *2026-10-25 — superseded an earlier draft where categories owned the
  pipeline: the operations board is per-site, not per-service-family.*
- **Locations** — the business may run multiple sites (shops, clinics,
  venues). A location is a `res.partner` record flagged
  `is_resource_location` (the barberhood precedent of partner-based
  sites): name, address, timezone and contact details come free.
  The flag lives in the shared `resource_location` module — the same
  site concept is used by the `resource_planning` suite (service
  posts), so a partner is marked once and seen by both apps, and
  planning assignments can feed resource–location presence directly.
  Every reservation is bound to one location (or videocall); slot
  search, list/calendar grouping and timezone handling are
  per-location, and the location's timezone is the reservation's
  timezone of truth (display, reminders, deadlines).
- **Resource–location assignment is schedule-based** — where a staff
  member works depends on the day (shop A Mon–Wed, shop B Thu–Sat).
  "Which resources are at this site" is a function of the slot's time
  and joins the availability intersection. Fixed-location resources
  (rooms, courts) are the all-hours degenerate case.
- **In/out flows** — *IN*: the customer comes to the location and the
  resource stays on-site (appointments; also multi-day stays — a hotel
  room is IN). *OUT*: the customer picks the resource up and takes it
  away (rentals, equipment loans). OUT changes the mechanics: the
  booked object is usually a pool of interchangeable units, the
  on-site events are pickup and return instead of check-in, and
  deposits become the common case. Multi-day durations are orthogonal
  to the flow (hotel IN, rental OUT).
  Home visits (staff travels to the customer) need no third direction —
  same flow, the reservation just carries a service address instead of
  a site. v1 keeps OUT minimal: booked out / expected back; overdue
  tracking, damage notes and per-day pricing are deferred to the
  `_rental` module.
- **Bookable resources** — unified over:
  - *staff* (`res.users` / `hr.employee`) — barbers, doctors, coaches;
  - *material* resources — courts, rooms, chairs, equipment;
  - *pools* of interchangeable units (a bike fleet, "table seats"
    qty 20) — a booking takes any K free units (items rented, guests
    seated); the customer does not pick a specific one;
  - each with its own calendar (`resource.calendar`), capacity, leaves,
    and schedule-based location assignment (a room is simply always at
    one site).
- **Functions (required capabilities)** — resources carry *flat*
  functions: what they can do (haircut, colorist, surgery-capable
  room); no levels — seniority stays a staff attribute (pricing,
  ordering), not a function tier. On a type, each required role is
  a standin for a resource to be reserved — one leg of the booking —
  and slot search/auto-assignment fills each leg with a resource
  carrying that function. With `hr`, each function maps to an employee
  skill (`hr.skill`, levels ignored) so the HR record stays the source
  of truth; material resources keep plain functions.
- **Legs (resource combinations)** — the type's required roles
  define the atomic set: the reservation is a *conjunction* of legs,
  each a function slot filled at booking time by one matching resource
  (doctor+room, court+coach). Leg properties:

  - **Cardinality** — a leg may demand more than one unit: pools cover
    interchangeable units (`quantity` seats, bikes), and the same
    mechanism extends to headcount legs ("2 movers", "3 ushers") when
    the pool abstraction doesn't fit.
  - **Alternatives** — a leg may accept a resource from a *set* of
    functions ("any exam room", "physician or resident") rather than a
    single function; matching uses the union of candidate functions.
    v1 may ship single-role legs only, but the model should not
    preclude alternatives.
  - **Optionality** — a required leg blocks booking if unfillable; an
    *optional* leg (the tennis coach) is filled when possible and
    simply drops out when no resource fits — the reservation keeps its
    remaining legs.
  - **Assignment mode** — auto assignment (sorted / least-used /
    random — `sequence` deprioritizes, e.g. senior staff last), manual
    pin by staff at booking time, or customer-driven choice in the
    catalog ("pick your barber"; "no preference" = auto).
  - **Occupied span** — each leg declares which segments occupy it
    (empty = all); the leg's *occupied interval set* is the unit of
    conflict, decoupled from the reservation's full-span envelope (see
    "Segmented service durations" below).
- **Capacity via pools** — seating is not modeled per-table: a location
  has a pool resource ("table seats", qty 20) and a booking consumes
  `guests` units of it for its duration. Same mechanism as rental
  fleets; no table-merge logic in v1.
- **Segmented service durations** — a type's duration is an ordered
  list of *segments* (`reservation.type.segment`: sequence, name,
  duration) rather than a single block — the Fresha
  "processing/finishing time" pattern, generalized (see the prior-art
  doc). Each required-function leg declares which segments occupy it
  (empty = all), so a colorist leg on "apply" + "finish" is free
  during "process" and another reservation can claim the gap.
  Segments also express legs that join mid-visit (nurse intake →
  doctor → nurse checkout: different legs per segment) and
  client-unattended gaps (a leg-less segment — spa lunch). The unit
  of conflict is the leg's *occupied interval set*, not the
  reservation span: each leg stores its segment-expanded intervals at
  schedule time — frozen against later type edits, auditable, and
  mirrored by the `calendar.event` projections.
- **Availability engine** — recurring weekly slots + one-shot slots;
  intersection of type schedule, resource calendars, resource–location
  schedules, leaves, existing bookings, and (optionally) planning
  shifts; slot granularity independent of reservation duration;
  durations may span days (hotel IN stays, rentals); optional
  buffer/handover time around bookings (cleaning, inspection);
  batch-computed for performance. The *full visit span* must fit the
  type/location schedule; per leg, only its occupied intervals must
  fit that resource's calendar minus leaves and other bookings — a
  staff member freed by a mid-service segment is genuinely bookable.
  Buffers wrap each occupied interval (a zero-buffer type keeps
  processing gaps fully reusable).
- **Reservation record** — a separate model, not a `calendar.event`:
  a booking must exist before a slot is chosen (invitation, waitlist),
  span several resources atomically, consume pool quantities, and carry
  stage/state — none of which an event expresses. Linked
  `calendar.event` records are synced for busy time, alarms and ICS —
  projections, not the truth. Audit via `mail.thread`.
- **Lifecycle** — a fixed `state` selection (draft, scheduled,
  in-progress, done, no-show, cancelled) is what automation and
  reporting rely on; the kanban-visible `stage` is configured per
  location and maps onto `state` — several stages may share a state
  (e.g. "Scheduled" and "Confirmed" both map to `scheduled`).
  Conflict detection; modification deadline.
- **Check-in / attendance** — mark in-progress (arrived / picked up)
  or done (completed / returned) plus no-show; drives KPIs and
  invoicing downstream.
- **Backend views** — calendar, gantt/resource-timeline grouped by resource,
  list, kanban by stage, form; popover actions (check-in, open order);
  DayPilot-style resource grid is the barberhood reference UX.

### Front-office (portal + public website)

- **Catalog flow** — public visitor browses service/reservation types
  (`/reservation` style pages), filtered by location/category — location is
  the primary entry point for multi-site businesses; picks resource (or
  "no preference"), slot, answers intake questions, confirms.
  This is the `website_appointment` model.
- **Invitation flow** — staff pre-creates a pending reservation and shares a
  tokenized link; the guest picks a slot. This is the `resource_booking`
  model. Both flows are needed.
- **Guest booking without account**; identified customers get `/my` pages:
  list upcoming/past, cancel (deadline-enforced), reschedule (old booking
  cancelled only after new one confirmed), book again.
- **Intake questions** — per-type question sets (text, select, checkbox),
  answers stored on the reservation.
- **Reminders & notifications** — per-type email/SMS alarms; SMS with tracked
  short link to the booking page; for OUT also pickup and return-due
  reminders; per-type control over staff notifications
  (barberhood learned staff don't want customer-facing mails).
- **Waitlist** — customer registers interest for a type + optional resource +
  date window + day-periods; on cancellation/new availability, offers go out
  (staff-notify, first-in-line, or first-to-claim); claim link books through
  the standard flow.
- **UX details proven in barberhood** — rich staff selector cards
  (avatar/bio/price), day-period pill filters, per-location timezone lock,
  intl-tel-input phone field, most-available-first ordering, deprioritized
  staff.

### Commercial

- **Product linkage** — a type maps to two `product.template` records: an
  optional **pre-payment product** (deposit collected at booking — also
  the rental security-deposit hook) and a **billing product** (invoiced
  at check-in); variants can encode staff seniority → different price
  per resource.
- **Pricing & payment** — display price on selection; if a pre-payment
  product is set, collect it at booking; on check-in create SO with the
  billing product → invoice → payment (or POS order). All payment
  integration lives in the `_sale` module.
- **POS integration** — book from POS, check-out a attended reservation as a
  POS order (barberhood `brb_pos_appointment`).

### Reporting

- Utilization/occupation rate per resource and shift; visits per customer;
  no-show rates; per-type booking counts. Stored aggregates or SQL views so
  pivot/graph views work (`occupation_rate` must never be SUM-aggregated —
  compute from summed components).

## 4. Comparison with OCA `resource_booking` (`~/work19/oca/calendar/resource_booking`)

OCA/calendar `resource_booking` (Tecnativa, Production/Stable, **AGPL-3**) is
the closest existing module. Its domain model is genuinely close to what this
app needs.

### What it already provides

- `resource.booking.type` — duration, availability `resource.calendar`,
  modifications deadline, meeting defaults, tags, alarms, per-company.
- `resource.booking.combination` — **multi-resource atomic booking**: a set of
  `resource.resource` records that must all be free; sorted auto-assignment.
  This directly covers doctor+room and court+coach.
- `resource.booking` — lifecycle with computed states
  (pending/scheduled/confirmed/canceled), auto meeting create/delete, conflict
  detection, modifiable/overdue flags, `mail.thread` + `portal.mixin`.
- **Invitation/portal flow** — backend creates a pending booking, requester
  schedules via `/my/bookings` or a tokenized URL (no user account needed).
- Two security groups (user/manager); honors resource calendars and leaves;
  integrates `hr` leaves and `mrp` work centers when installed.

### Gaps vs. this app's requirements

| Capability | `resource_booking` | Needed |
| --- | --- | --- |
| Public catalog self-service (browse → pick → book) | ✗ invitation-only | Required (barber, salon, tennis, restaurant) |
| Customer chooses resource/staff | roadmap item ("allow customer to choose combination") | Required, incl. "no preference" |
| Staff-as-resource (users/employees) | books `resource.resource` only | Need staff identities w/ bio, display name, seniority |
| Required functions / skills matching | ✗ combinations are fixed resource sets | Required (qualified staff only, room capabilities) |
| Capacity / party size | ✗ combination is all-or-nothing, no seat counting | Required for restaurant |
| Multi-location | ✗ per-company only | Required (chains: types, resources and slots are per-site) |
| Rental / OUT flow | ✗ meeting-oriented, single-visit lifecycle | Required (unit pools, multi-day, pickup/return, deposits) |
| Check-in, attended/no-show | ✗ (no post-event states) | Required |
| Configurable stage pipeline | ✗ fixed computed states | Required (per-category pipelines; states stay fixed for automation) |
| Intake questions | ✗ | Required (clinic, salon) |
| Products, pricing, payment, SO/POS checkout | ✗ | Required |
| Waitlist | ✗ | Required (barberhood roadmap) |
| Email/SMS templates per type, staff-notification control | basic alarms only | Required |
| Frontend UX polish (period filters, cards, tz lock) | minimal portal pages | Required |
| Reschedule & book-again portal ops | cancel only (via meeting) | Required |
| Planning-shift gating, occupation KPIs | ✗ | Required (barberhood) |
| **License** | **AGPL-3** | **LGPL-3 target** |

### Strategic assessment

- `resource_booking`'s **combination model is the right kernel** — it already
  solves the clinic and tennis use cases that the Enterprise app handles
  awkwardly. But it is architected "invitation-first": the record exists before
  the customer sees a calendar. The catalog flow needs the inverse — slot
  search *before* any record exists.
- *2026-10-25 — update:* the kernel assessment no longer holds. Its
  combinations are enumerated sets of concrete resources; this app fills
  role legs with any matching resource (5 doctors × 3 rooms would
  need 15 combination records in its model). Pools, stage pipelines,
  locations, in/out flows and check-in have no counterpart. What remains
  reusable is thin scaffolding — record + meeting sync + portal token —
  that a fresh module writes anyway.
- The **license mismatch is the hard blocker**: it is AGPL-3, the target is
  LGPL-3. An LGPL module extending/depending on it produces an effectively-AGPL
  combined work, and OCA will not accept an LGPL addon riding on AGPL.
  Options:
  1. **Ask Tecnativa/OCA to dual-license or relicense** `resource_booking` as
     LGPL — clean if granted, unlikely.
  2. **Accept AGPL for the core** (`resource_booking` as dependency) and keep
     only new LGPL modules on top — defeats the LGPL goal.
  3. **Fresh LGPL implementation** reusing the *concepts* (types,
     combinations, availability calendars) but not the code — most work, but a
     clean license and freedom to design catalog-first.
  4. **Fork-and-relicense is not an option** without all authors' consent.
- Its declared roadmap items (customer-chosen combination, least-used
  assignment, better error messages, batched busy-interval computation) confirm
  the module is at the edge of its intended scope — it was built for managed
  bookings, not consumer self-service.

**Decision (2026-10-25):** option 3 — fresh LGPL core (confirms the
earlier preliminary recommendation). Relicensing (option 1) is not
pursued: it would pay the negotiation cost and still leave the
architectural surgery. `resource_booking` stays the best *reference* —
read its availability engine for TZ/DST, leaves and interval-math edge
cases — but is not a base.

## 5. Proposed module map (sketch)

Following OCA granularity and the barberhood precedent of small modules:

| Module | Depends on | Contents |
| --- | --- | --- |
| `resource_location` | `resource` | Shared `is_resource_location` partner flag — the site concept used by this family and `resource_planning` |
| `resource_reservation` | `calendar`, `mail`, `resource`, `resource_location`, `portal` | Core: types, categories & stage pipelines, locations, in/out flows, resources (incl. pools), functions, combinations, availability engine, reservation record, lifecycle, backend views, invitation flow |
| `resource_reservation_rental` | core (+ `resource_reservation_sale`) | Later-phase OUT extras: per-day pricing, security deposits, overdue tracking, return-condition |
| `resource_reservation_website` (or `website_resource_reservation`) | + `website` | Public catalog, slot picking, guest booking, questions, staff cards, period filters |
| `resource_reservation_portal` | + `portal` | `/my` bookings: cancel, reschedule, book again |
| `resource_reservation_sale` | + `sale_management` | Product/variant linkage, pricing, prepay, SO on check-in |
| `resource_reservation_pos` | + `point_of_sale` | POS booking and checkout |
| `resource_reservation_hr` | + `hr(_holidays, _skills)` | Employee resources, leave gating, planning-shift availability, functions mapped to `hr.skill` |
| `resource_reservation_waitlist` | core + `sms` optional | Waitlist entries, matching, offers, claim |
| `resource_reservation_kpi` | core (+ hr/planning) | Occupation, visits, no-show reporting |

Naming: decided — `resource_reservation`, in the `oca/resource` repo,
LGPL-3, author Daniel Reis. (`resource_booking` is taken by the OCA
module and is AGPL; `booking` / `reservation` were the other
candidates.)

## 6. Migration path from barberhood (later phase)

- `calendar.event`-centric barberhood data maps to `reservation` records +
  linked events; `appointment_booker_id` → `reservation.partner_id`.
- `appointment.type` → `reservation.type`; `staff_user_ids` → staff resources;
  `service.category` → `reservation.category` (grouping only; stage
  pipelines live on locations); slot periods, no-preference,
  deprioritized users, seniority pricing → first-class fields per §3.
- Barberhood locations are `res.partner` records linked m2m to
  `appointment.type` (staff derived via the types); the new app keeps
  partner-based locations and makes resource–location assignment
  schedule-based, first-class data.
- Portal pages `/my/appointments` → `/my/bookings` (or keep both routes during
  transition).
- Keep `web_daypilot`/`web_gantt_precision` as independent view modules — they
  are already LGPL and orthogonal.
- Enterprise `appointment`/`website_appointment` become uninstallable once
  parity is reached — this removes the OEEL dependency entirely.

## 7. Open questions

- **`draft` is overloaded.** It currently means three things: a slot
  hold (has `hold_expiration`), a customer request awaiting staff
  confirmation ("Requested" pipeline stage), and — if phase-6
  waitlist reuses it — a desired-slot queue entry. The hold/waitlist
  mechanics work on drafts already (desired window, no assigned
  resources, survives the hold cron when `hold_expiration` is empty,
  Requested column shows the queue). The question is whether to keep
  `is_waitlist`-style flags or split `requested` into its own state
  so `draft` means strictly "hold/unconfirmed" — decide when the
  waitlist feature lands.

## 8. Implementation phasing

Ordered by dependency, with the riskiest piece — the availability
engine — proven early. Module names per §5.

**Phase 0 — naming & skeleton**

- Decided: family name `resource_reservation`, `oca/resource` repo,
  LGPL-3, author Daniel Reis.
- Empty module skeletons, CI.

**Phase 1 — core (`resource_reservation`)** *(in progress — models,
engine, views, invitation flow, demo data and tests landed)*

- Data model: categories + stage pipelines, types, locations
  (`res.partner`), resources (staff / material / pool with qty),
  functions, schedule-based resource–location lines.
- Reservation record: fixed `state`, per-category `stage`, `guests`,
  partner, location, resource legs; `mail.thread`, portal token.
- `calendar.event` sync (projection only).
- Availability engine: batch slot search over the §3 intersection
  (type schedule, resource calendars, resource–location schedules,
  leaves, bookings, buffers); multi-day (hotel-style IN stays, OUT
  rentals). Built on per-leg occupied intervals as the conflict unit
  from the start (phase-1 legs hold a single `[start, end)` interval
  each), so the phase-1b segment expansion is purely additive — no
  data migration.
- Check-in / attendance actions; backend views (form, list, kanban by
  stage, calendar, resource timeline).
- Invitation flow (tokenized portal link) — simplest customer path;
  proves the core end-to-end without a website.
- *Test focus:* availability edge cases — TZ/DST, leaves, overlaps,
  pool quantities. Borrow `resource_booking`'s test scenarios as a
  checklist.
- *Exit:* staff creates a pending reservation, guest schedules it via
  link, check-in / no-show is recorded.

**Phase 1b — segmented services**

- `reservation.type.segment` (sequence, name, duration); when a type
  has segments, its `duration` is their sum — a type with no segments
  behaves as today (one implicit segment over `duration`). Leg
  definitions on the type declare occupied segments (empty = all), so
  adding segments never silently drops a leg.
- Legs expand occupied intervals at schedule time and store them —
  the phase-1 engine already conflicts on leg intervals, so this is
  additive: type data + expansion + views, no migration.
- Views: segment editor on the type form (ordered segments × legs
  matrix); timeline renders gap segments hatched inside the
  reservation block; "currently in segment X" derived from `now()`
  for the front-desk board. Catalog unchanged — customers see the
  total duration and simply get more slots.
- *Test focus:* claiming a processing gap with another booking;
  legs in non-contiguous segments; leg-less gap segments; buffer
  interplay; pool quantities per segment; type edits vs frozen
  intervals on scheduled reservations.
- Depends on: phase 1. Independent of phases 2–5; barberhood has no
  counterpart — a fresh capability. Primary verticals: color-processing
  salons (staff freed during "process"), medical clinics (sequential
  nurse/doctor legs), vehicle service bays (mechanic legs on
  inspection/reassembly, gaps while waiting), spas (unattended
  gap segments).

**Phase 2 — public catalog (`resource_reservation_website`)**

- `/reservation` pages filtered by location/category; resource choice incl.
  "no preference"; slot picker; guest booking; intake questions.
- Barberhood-proven UX: staff cards, day-period pills, location tz
  lock, intl phone field, most-available-first ordering.
- Depends on: phase 1.

**Phase 3 — customer portal (`resource_reservation_portal`)**

- `/my` bookings: upcoming/past, cancel (deadline-enforced), reschedule
  (two-step), book again.
- Reminders & notifications: per-type email/SMS, tracked short links,
  staff-notification control; pickup / return-due for OUT.
- Depends on: phase 1 (phase 2 for the full guest path).

**Phase 4 — commercial (`resource_reservation_sale`, `_pos`)**

- Product linkage: pre-payment + billing products, variant→seniority
  pricing; price display on selection.
- Deposit collected at booking; SO → invoice → payment on check-in;
  POS booking & checkout.
- Depends on: phase 1 (phase 2 for customer-facing pricing).

**Phase 5 — HR (`resource_reservation_hr`)**

- `hr.employee` resources, leave gating, planning-shift availability,
  function ↔ `hr.skill` mapping.
- Depends on: phase 1; can run in parallel with phases 2–4.

**Phase 6 — growth (`_waitlist`, `_kpi`, `_rental`)**

- Waitlist: entries, matching on cancellation/new availability, offers,
  claim flow.
- KPI: occupation rate (never SUM-aggregated), visits per customer,
  no-show rates.
- Rental extras: overdue tracking, return-condition, per-day pricing.
- Depends on: phase 1; `_rental` also needs phase 4 billing.

**Phase 7 — barberhood migration**

- Data migration per §6; transitional portal routes; Enterprise
  `appointment` / `website_appointment` uninstall once parity holds.
- Depends on: phases 1–4 parity (+ 5 for staff-driven availability).

**Demo data** — each vertical from §2 gets demo records, so every
distinctive mechanism is exercisable out of the box:

- Barber shop (IN, one location): staff resources with functions
  (cut, color), "no preference" flow, seniority pricing variants.
- Beauty salon: staff + room combination, multi-service types.
- Medical clinic: role legs (physician + exam room), intake
  questions.
- Tennis club: material-only resource; optional coach leg.
- Restaurant: seat pool (qty), party-size `guests`, lunch/dinner
  seating turns.
- Hotel: room resource, multi-night type, housekeeping buffer.
- Rental shop: OUT type, unit pool, deposit (with `_sale` demo).
- Multi-location: two shops, rotating staff via schedule-based
  resource–location lines.

Each module ships the demo records for the mechanisms it introduces:
core covers IN + multi-location + pools; `_rental` and `_sale` cover
the OUT commercial flows.

## 9. Implementation notes — relevant Odoo `resource` primitives

Verified against Odoo 19.0 community source (`~/work19/odoo/addons`).

### `resource` (core dep)

- `resource.resource` — base entity. `resource_type` already splits
  `user`/`material`; `user_id`, `company_id`, `calendar_id` (empty =
  fully flexible), `tz`, `time_efficiency`. `res.users` exposes
  `resource_ids`. Our staff/material resources can *be*
  `resource.resource` records (the `resource_booking` approach) — the
  pool-with-quantity extension is ours.
- `resource.calendar` — the work schedule: weekly `attendance_ids`
  (`dayofweek`, `day_period` morning/afternoon/night,
  `hour_from`/`hour_to`, `week_type` for two-week rosters,
  `date_from`/`date_to`), `leave_ids`, `global_leave_ids`
  (company-wide holidays), `tz`. Variants: `two_weeks_calendar`,
  `schedule_type` fixed/flexible, `duration_based`.
- `resource.calendar.leaves` — time off; `calendar_id` and
  `resource_id` both optional (calendar-wide, per-resource, or
  company-global).
- `resource.mixin` — `resource_id` + `resource_calendar_id` + `tz`
  for any model; `hr.employee` uses it.
- **Interval API** — all batch, all returning `Intervals`
  (`odoo.tools.intervals`: ordered disjoint intervals, each carrying a
  recordset; `|`, `&`, `-` operators):
  - `calendar._attendance_intervals_batch(start, end, resources)`;
    `._leave_intervals_batch(...)`;
    `._work_intervals_batch(..., compute_leaves=True)` (attendance −
    leaves); `._unavailable_intervals_batch(...)`.
  - `resource._get_valid_work_intervals(start, end)` — resolves a
    resource's calendar *validity over time* (calendars can change);
    `._adjust_to_calendar`, `._get_closest_work_time`,
    `calendar.get_work_hours_count`.
  - This is the engine's foundation: slot search ≈ type schedule
    windows `&` per-leg `_get_valid_work_intervals` `&` location
    schedule `-` existing bookings — same shape as `resource_booking`'s
    engine, but driven per function leg and per pool quantity.
- **Functions: nothing in core.** No role/function/skill model in
  community `resource`. `hr.job` is one position per employee — too
  coarse. Flat `resource.role` is new data; `hr_skills` is only
  the mapping target.

### Leaves without employees

`resource.calendar.leaves` is the generic unavailability mechanism —
`hr.leave` is just one *producer* of it (the employee approval
workflow). Any `resource.resource` takes leaves directly; three
scopes (from `_leave_intervals_batch`):

- `resource_id` set → that resource only (court under maintenance);
- `calendar_id` + empty `resource_id` → every resource on that
  calendar — with a calendar per location, this is "site closed";
- both empty → company-global (public holidays).

Two rules: `time_type` must be `leave` (the default) — `other` counts
as work time and does not block; recurring closures belong in the
calendar's attendance lines (`date_from`/`date_to`), leaves are for
exceptional blocks. Material resources have no request workflow —
managers create leaves directly (backend "block time" action on the
resource form / timeline). For pools, a resource-level leave blocks
the whole pool; a single broken unit is better modeled as an internal
reservation consuming one unit.

### HR modules (for `resource_reservation_hr`)

- `hr.employee` → `resource.mixin`. In 19 the calendar sits on
  `employee.version_id`, giving *calendar periods* over time —
  matches the schedule-based location design.
- `hr.work.location` exists, but is a single static field per
  employee — not schedule-based; our resource–location lines are
  still needed.
- `hr_holidays`: approved `hr.leave` auto-creates
  `resource.calendar.leaves` — leave gating is free once the bookable
  resource links to the employee's `resource_id`.
- `hr_calendar` (community): `res.partner._get_schedule(start, stop)`
  merges employee work intervals **and `calendar.event` attendee busy
  time** — our synced event projections plug into the same pattern.
- `hr_homeworking` (optional): employees declare home/office days —
  adjacent to schedule-based location; review for reuse.
- `hr_skills`: `hr.skill` / `hr.skill.type` / `hr.skill.level`;
  `hr.employee.skill` lines carry `skill_level_id`,
  `valid_from`/`valid_to`, certifications (new in 19). Flat function →
  `hr.skill` mapping ignores levels.

### What core does *not* give us

Pools/quantities, per-type availability schedules (a dedicated
`resource.calendar` per type is the natural implementation), location
schedules, cross-leg slot search, stage pipelines, check-in/return
lifecycle. The `Intervals` machinery covers the hard math; the domain
model is ours.
