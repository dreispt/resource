To configure this module:

1. **Categories** — go to *Reservations → Configuration → Categories*
   and create the categories grouping your reservation types.
2. **Functions** — in *Configuration → Functions*, create the
   capabilities resources can have (e.g. "Haircut", "Exam room").
3. **Locations** — locations are partners. In *Configuration →
   Locations* (or Contacts), create a partner per site, set its
   timezone, and configure its stage pipeline on the *Reservation
   Pipeline* tab: ordered stages, each mapped to a fixed state
   (draft, scheduled, in progress, done, no-show, cancelled). Slot
   times are displayed in the location's timezone.
4. **Resources** — in *Reservations → Resources*, mark
   `resource.resource` records bookable and set their functions,
   quantity (for pools), and location-schedule lines (which location
   they work at, on which calendar). A resource with a single
   always-true line is a fixed-location resource.
5. **Reservation types** — in *Configuration → Reservation Types*,
   set duration, the required roles (one leg each), availability
   calendar, booking window (min notice / max horizon), cancellation
   deadline, locations offered, and message templates.
6. **Blocking time** — create `resource.calendar.leaves` on a resource
   (maintenance), on a location calendar (site closed), or globally
   (public holidays). Recurring closures belong in the resource's
   calendar attendance lines instead.
