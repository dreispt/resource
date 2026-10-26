## Creating a reservation

1. Go to *Reservations → Reservations* and click *New*.
2. Pick the **type** and **location**, and the customer (**partner**).
3. Fill the role legs: pick a resource for each required role,
   or leave them empty for auto-assignment when the slot is picked.
4. Pick a slot (from availability) or set start/stop directly.

The reservation moves through its category's stages; each stage maps
to a fixed state used by automation and reporting.

## Invitation flow (guest self-scheduling)

Create a draft reservation with a partner and a type — no slot yet.
Share the tokenized link (from the form). The guest opens the link,
picks a slot from the type's availability, and confirms. No account
is needed.

## Check-in and attendance

- **IN** reservations: mark *Attended* when the customer arrives, or
  *No-show* if they don't. OUT reservations use *Picked up* and
  *Returned* instead.
- Check-in drives KPIs and, with the sale module, invoicing.

## Cancelling and rescheduling

Cancel from the reservation form or the kanban card — the linked
calendar event is removed automatically. Reschedule by picking a new
slot; the event projection follows.
