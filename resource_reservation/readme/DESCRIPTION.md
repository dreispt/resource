Reserve resources for a time slot: staff members, rooms, equipment,
or pools of interchangeable units. Reservations can be created by
staff, or scheduled by the customer through a tokenized invitation
link — no account needed.

Features:

- **Reservation types**: duration, availability calendar, booking
  window rules, cancellation deadline, locations where offered.
- **Categories and stage pipelines**: types are grouped in categories;
  each category configures its own ordered stages, mapped to a fixed
  list of states that automation and reporting can rely on.
- **Multiple locations**: locations are partners (addresses with
  timezone); resources are assigned to locations on a schedule — a
  barber can work at shop A on weekdays and shop B on Saturdays.
- **Bookable resources**: staff (users/employees), material resources
  (rooms, courts), and pools of interchangeable units with a quantity
  (a bike fleet, "table seats").
- **Functions**: flat capabilities on resources; a type requires
  functions, and each required role is a leg of the booking filled
  by a matching resource (doctor + exam room).
- **In/out flows**: *IN* reservations happen on-site (appointments,
  multi-day stays); *OUT* reservations take the resource away
  (rentals), with pickup/return instead of check-in.
- **Capacity**: a pool with quantity N serves bookings consuming K
  units — party-size seating and multi-unit rentals share the same
  mechanism.
- **Lifecycle**: fixed states (pending, scheduled, confirmed,
  attended, cancelled, no-show, picked-up, returned) drive automation;
  check-in and attendance actions; synced `calendar.event` for busy
  time, alarms and ICS.
- **Guest scheduling**: pending reservations get a tokenized link the
  requester uses to pick a slot themselves.

## Comparison with `resource_booking`

This module is an alternative implementation of the problem solved by
`resource_booking` (in `oca/calendar`). The two are independent and
can coexist — nothing here depends on it.

| | `resource_booking` | `resource_reservation` |
| --- | --- | --- |
| License | AGPL-3 | LGPL-3 |
| Booking flow | Invitation-first (record exists, then requester picks a slot) | Invitation *and* catalog self-service (slot search before any record) |
| Resource matching | Enumerated combinations of concrete resources | Function legs filled by any matching resource |
| Customer-chosen resource | Roadmap item | Built-in, incl. "no preference" auto-assignment |
| Locations | Per-company only | Multi-location, schedule-based resource assignment |
| Quantities | All-or-nothing resource sets | Pools: quantity on resource, consumption per booking |
| Lifecycle | Fixed computed states | Per-category stage pipelines over fixed states; check-in / attended / no-show / pickup / return |
| Flow | Meetings only | IN (appointments, multi-day stays) and OUT (rentals) |
| Commercial | — | Product linkage, deposits, SO/POS checkout (addon modules) |
| Booking record | Separate record + linked meeting | Same shape — separate record syncing to `calendar.event` |

## Why a fresh implementation

- **License.** The target is LGPL-3 so the app can be reused freely;
  `resource_booking` is AGPL-3, and an LGPL addon cannot depend on it.
- **Architecture divergence.** Catalog-first slot search (before any
  record exists), function-leg matching instead of enumerated
  combinations, pools, stage pipelines and locations are all core
  assumptions — retrofitting them into `resource_booking` would mean
  surgery on its data model, not extensions on top of it.
- **Still a reference.** Its availability engine's handling of
  timezones, leaves and interval math informed this implementation.
