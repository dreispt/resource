# Resource Service Planning — specifications

**Status:** in progress
**Date:** 2026-10-25
**Scope:** a reusable service-planning framework for Odoo — planning work
against generic resources rather than requiring employees. The base
addon `resource_planning` manages assignments; demand, rotations and
UI or HR integrations live in optional addons.
**Target platform:** Odoo 19.0
**Target ecosystem:** Odoo Community Association (OCA)
**Base addon:** `resource_planning`
**Architectural principle:** resource-first planning, with HR as an
optional integration layer.
**Related:** `resource/resource_reservation/readme/specs.md` (sibling design —
reservations / booking surface; this doc owns *planning* — allocating
resources to service demand over time);
`docs/RESOURCE_SERVICE_PLANNING_PRIOR_ART.md` (terminology survey
across planning products).

## 1. Objectives

Develop a reusable service-planning framework for Odoo that supports
planning work against generic resources rather than requiring employees.

The module must support:

- Defining recurring or one-off service demand.
- Representing dated services independently of assignments.
- Assigning resources to services, including ad hoc assignments.
- Expressing staffing requirements, roles and qualifications.
- Detecting conflicts, availability constraints and coverage gaps.
- Supporting grid, matrix, timeline and calendar planning interfaces.
- Adding HR-specific functionality through an optional addon.
- Allowing other OCA modules to extend the framework without depending on
  a particular planning interface.
- Defining reusable rotation patterns and applying them to resource
  planning without making rotations mandatory.

The initial implementation targets Odoo 19.0.

### Non-goals for the initial release

- Automatic workforce optimisation.
- Advanced constraint-solving algorithms.
- Payroll, attendance or timesheet management.
- A mandatory dependency on `hr`.
- A mandatory third-party scheduling library.
- A complete rotation-management system in the initial release.

## 2. Architecture and naming conventions

### 2.1 Resource-first foundation

The base addon depends on `resource` and `resource_role`, not `hr`.

All new persistent business models introduced by this project must use a
technical model name beginning with `resource.`. This convention applies
to core models and models introduced by optional integration addons.

For example:

- `resource.service.schedule`
- `resource.position.slot`
- `resource.service.assignment`
- `resource.service.requirement`

Use the corresponding `resource_...` prefix for addon technical names.

The existing Odoo model `resource.resource` remains the generic resource
abstraction. Do not introduce a replacement resource model.

### 2.2 Addon structure

| Addon | Dependencies | Responsibility |
|---|---|---|
| `resource_planning` | `resource`, `resource_role` | Assignments: resource-to-interval allocations, conflict and availability validation, the roster grid engine, and the shared `resource.service.period` vocabulary |
| `resource_planning_demand` | `resource_planning` | Demand: service locations, positions, dated slots (`resource.position.slot`), requirements, schedules and service generation; injects `service_id`/`requirement_id` onto assignments |
| `resource_planning_rotation` | `resource_planning` | Rotation plans — crew codes × cycle days mapped to day periods — applied to resources |
| `resource_planning_demand_rotation` | `resource_planning_demand`, `resource_planning_rotation` | Glue: positions as rotation hosts, crew members holding matrix codes |
| `resource_planning_matrix` | `resource_planning_rotation`, `web_widget_x2many_2d_matrix` | Optional 2D matrix views for rotation plans |
| `resource_planning_timeline` | `resource_planning_demand`, OCA `web_timeline` | Optional timeline interface |
| `resource_planning_daypilot` | `resource_planning` and any required integration dependencies | Optional DayPilot implementation, only if justified |
| `resource_planning_hr` | `resource_planning` and `hr` | Employee integration and HR-specific availability and eligibility |

Dependency rules:

- The base addon must not depend on any other addon of the family.
- `resource_planning_rotation` must not depend on
  `resource_planning_demand`: rotations over day periods are a
  self-contained planning aid. This is why `resource.service.period` —
  used both by demand schedule lines and by rotation cells — lives in
  the base addon.
- `resource_planning_demand_rotation` is the only addon bridging
  rotations and demand: positions become rotation hosts and gain crew
  members there.
- `resource_planning_position` is dissolved: locations and positions
  move to the demand addon, rotation-on-position glue to
  `resource_planning_demand_rotation`.

The optional UI addons should be implemented only when the corresponding
functionality is needed. Do not create empty or speculative addons merely
to reserve names.

## 3. Domain model

The design separates four planes that must not be conflated:

- **Demand** (`resource_planning_demand`): a tree of service locations,
  service positions and day periods, carrying work requirements — the
  open slots. Day periods split the day between multiple resources.
- **Planning** (`resource_planning_rotation`): rotation plans applied to
  positions and day periods — each day period on each day maps to a
  crew code.
- **Supply** (`resource`): resources with work availability — the
  calendars and leaves that decide which slots a resource can cover.
- **Assignments** (`resource_planning`): a `resource.resource` allocated
  to a crew code in a service position for a period of time —
  concretely, an explicit `[start, end)` interval, optionally
  fulfilling a demand slot.

A dated service can exist without an assignment. An assignment can also
exist without any demand: ad hoc work is always supported.

### 3.1 Service locations

Locations are `res.partner` records flagged `is_resource_location` — the
shared flag from `resource_location`, also used by
`resource_reservation`. They carry the site
context (address, timezone) for positions and dated services.

### 3.2 `resource.service.position`

A post to fill inside a location, e.g. "Gate A" or "Reception".

Each position carries:

- Its location (`location_id`) and company.
- A default role.
- The schedule generating its dated services.
- When the rotation glue is installed: dated rotation applications and
  the crew mapping resources to matrix codes.

### 3.3 `resource.service.period`

A named day period such as Morning, Evening or Night, with a short
display `code` and an `is_day_off` flag.

Day periods split the day between resources: a 24/7 post is staffed by
several periods. Periods are shared vocabulary — demand uses them on
schedule lines, rotations map cycle days to them — so the model lives
in the **base** addon, letting `resource_planning_rotation` work
without the demand addon.

Concrete period times are position/schedule-specific and live on
`resource.service.schedule.line`, not on the period itself.

### 3.4 `resource.service.schedule`

Defines service demand over time — not the allocation of a specific
resource.

Responsibilities:

- Define the recurrence: daily or weekly, interval N, explicit
  `anchor_date`, weekday flags for weekly, per-schedule
  `horizon_days`.
- Carry default requirements, as requirement rows with `schedule_id`
  set (templates copied onto generated services).
- Carry schedule lines (`resource.service.schedule.line`): one per
  period to staff on each pattern date, each with its own local start
  time, duration, role and headcount. A schedule without lines
  generates one service per date from its default start/duration.
- Control the generation of dated services — idempotent, create-only.

A schedule may generate many services. One-off services are supported
without requiring a recurring template.

### 3.5 `resource.position.slot`

A dated demand cell: one (position, day period, date) slot to staff —
the "service" is a dated instance of a position's day period, the same
concept at different levels of the demand tree. It is the principal
dated object used by planning interfaces.

Key fields:

- `position_id`, `location_id` (stored), `schedule_id`, `line_id`,
  `period_id` — all optional.
- `start_datetime` and `end_datetime` — required.
- `state`: draft, planned, published, completed or cancelled.
- `requirement_ids`, `assignment_ids`.

A service can exist without position or schedule: one-off,
positionless demand is supported.

### 3.6 `resource.service.requirement`

Defines the coverage needed for a service — an open slot.

Key fields:

- Exactly one parent: `service_id` XOR `schedule_id` (template).
- `role_id`, where a specific role is required.
- `quantity`: required headcount.
- Optional interval overrides when the requirement covers only part of
  the service.

Requirements must exist independently of assignments so that an
unfilled position can be represented explicitly. If a service requires
three resources and only two are assigned, the system reports a
shortfall of one — it must not create a fictitious third resource or
an assignment without a resource merely to represent the gap.

### 3.7 `resource.service.assignment`

The base addon's central record: an allocation of a generic resource
to an explicit `[start_datetime, end_datetime)` interval with a
lifecycle state.

In the base addon the assignment has **no demand links** — it carries
`resource_id`, the interval, `state`, `role_id`, notes and the
conflict/warning machinery. `resource_planning_demand` injects
`service_id`, `requirement_id` and `period_code`; rotation glue may
add crew-code links. Ad hoc assignments stay fully usable standalone.

The assignment interval is explicit. Do not rely exclusively on the
service interval: a resource may cover only part of a service.

### 3.8 `resource.role`

Provided by the `resource_role` addon — a planning role such as
technician, supervisor, operator or driver.

Roles describe the function a resource is expected to fulfil. They are
not inherently HR job positions.

A requirement can specify a role, and an assignment can record the
role fulfilled where this is necessary to support validation and
reporting. Resources declare the roles they can fulfil through
`resource.resource.role_ids`.

### 3.9 Qualifications

The planning framework may need to represent qualifications such as
certifications, authorisations or other eligibility conditions.

Before creating qualification models, investigate the existing OCA
resource ecosystem and reusable abstractions.

If no appropriate abstraction exists, introduce resource-prefixed
models, for example:

- `resource.service.qualification`: defines a qualification used by
  planning.
- `resource.service.resource.qualification`: associates a generic
  resource with a qualification, including validity dates where needed.

The exact model structure should be confirmed during implementation.
Qualification validity and assignment eligibility must be evaluated
independently of HR.

### 3.10 Rotation planning

`resource.service.rotation` is a reusable matrix: crew codes (rows —
`resource.service.rotation.crew`, e.g. A, B, C, D) × cycle days, each
cell (`resource.service.rotation.cell`) mapping to a
`resource.service.period`, including day-off periods. Templates are
ordinary editable records; popular patterns ship as editable
`noupdate` data organised by `resource.service.rotation.tag`.

`resource.service.rotation.application` puts a plan in effect for a
date range on a host. Hosts are extensible through the
`resource.service.rotation.host` mixin: resources natively in
`resource_planning_rotation`; positions additionally in
`resource_planning_demand_rotation`, where
`resource.service.rotation.member` maps a resource to each crew code
("Alice = A"). `current_rotation_id` resolves the plan in effect
today.

The initial default data ships a small set of popular, generic
patterns — 5-on/2-off, 4-on/4-off, 7-on/7-off, 14-on/14-off, 2-2-3,
weekly alternating shifts — as ordinary editable records, not
hard-coded behaviour, not required for ordinary service planning.

The design must keep defining:

- How exceptions, absences and manual overrides are represented.
- Whether a rotation generates demand, suggested assignments or only
  availability indicators — crew-code assignment generation is
  roadmap work (§9).
- How changes to a rotation affect future generated records without
  overwriting published or manually edited planning data.

Do not conflate a rotation template, a service schedule and a resource
assignment. A rotation can help generate a plan, but it must not become
a mandatory prerequisite for ordinary planning.

## 4. Temporal semantics and validation

### 4.1 Time intervals

Use explicit start and end datetimes for assignments and dated
services.

Adopt half-open intervals:

`[start_datetime, end_datetime)`

Two adjacent assignments ending and starting at the same instant
therefore do not overlap.

Validate that the end is later than the start. Handle timezone conversion
consistently using Odoo's standard datetime conventions.

Rotation lines that represent dated work or rest periods must use the
same timezone and interval conventions as services and assignments. A
rotation cycle must have an unambiguous anchor date and must not silently
change meaning when viewed in another timezone.

### 4.2 Conflict detection

The core must provide reusable operations to identify overlapping
assignments for the same resource.

The initial policy should distinguish between:

- Hard conflicts, which prevent an assignment from being confirmed or
  published.
- Warnings, which inform the planner but may be overridden.
- Informational conditions, such as potential coverage shortfalls.

The exact conflict policy should remain extensible. Some resource types
may permit concurrent allocations under particular circumstances, while
others may not.

Concurrency-sensitive validations must be enforced server-side.
Client-side warnings are not sufficient.

Rotation-derived suggestions must be validated against the same conflict
and availability rules as manually created assignments. A rotation must
never bypass ordinary assignment validation.

### 4.3 Availability and eligibility

The core should expose extension points for determining resource
availability and eligibility.

Potential checks include:

- Existing assignments.
- Resource working calendars, where applicable.
- Resource-specific availability.
- Required roles and qualifications.
- Resource active status.
- Extension-provided constraints.
- Rotation state, including whether the resource is in a work, rest,
  standby or exception period.

Do not assume every resource is a person or has employee working hours.
HR-specific availability and leave rules belong in the HR integration
addon.

### 4.4 Coverage calculation

Coverage is calculated by comparing requirements with eligible
assignments over time.

The system must distinguish:

- Required capacity.
- Assigned capacity.
- Eligible assigned capacity.
- Unfilled capacity.
- Over-allocation or other constraint violations.

For interval-based requirements, coverage must be evaluated across the
relevant time segments. A single total headcount for an entire day can
hide gaps during individual hours.

Coverage calculation should be reusable by forms, grids, reports and
external integrations.

### 4.5 Daily roster status

The status of a roster cell — a position on a given day and period —
is **not** a trivial lookup. It must cross four inputs that live in
different addons:

- **Position requirements** (demand): the open slots demanded for that
  cell — `resource.position.slot` rows and their
  `resource.service.requirement` headcounts.
- **Rotation plan** (rotation glue): the crew code the position's
  rotation application maps to that day and period.
- **Assigned resources** (base + glue): who holds the crew code
  (rotation member) and who is actually allocated
  (`resource.service.assignment`).
- **Availability** (supply): whether the assigned resource can cover
  the period — working calendar, leaves, conflicting assignments.

Because the inputs span `resource_planning`, `resource_planning_demand`
and `resource_planning_demand_rotation`, the status must be computed
through shared server-side operations — the
`resource.service.roster` engine extended per layer — never assembled
ad hoc in views. Each layer contributes its own enrichment, and the
result must stay correct when a layer is absent: a position without a
rotation has no crew code to cross, a slot without assignments is open
demand, a member without an assignment is planned-but-unallocated, and
an assigned resource on leave does not count as covered.

## 5. Planning interfaces

Planning views are a first-class design concern, but they must remain
separate from the domain model and server-side business operations.

The initial interface strategy targets Odoo 19.0.

### 5.0 Key screens — prior art

Every major scheduling product opens on the same screen: a **roster
grid** — resources (people or positions) as rows, time as columns.
Two families:

- **Cell rosters** (SMB tools): cells hold a shift per position/person
  per day.
  - *Deputy* — Schedule tab: team members or areas in the left column,
    days on top; location/area selector; day/week/2-week/month views.
    ([help.deputy.com](https://help.deputy.com/hc/en-au/articles/4688713423759-Schedule-overview))
  - *7shifts* — employees grouped by role, weekday columns,
    location→department→role filters, "+" cells create shifts inline.
    ([kb.7shifts.com](https://kb.7shifts.com/hc/en-us/articles/31634882661907-7shifts-101-How-to-navigate-the-Schedule))
  - *When I Work* — Scheduler with **Users / Positions / Job Site /
    Coverage** staff views — a positions-as-rows mode (the guard model)
    plus a coverage-ordered view.
    ([help.wheniwork.com](https://help.wheniwork.com/articles/schedule-views-computer/))
- **Gantt dispatch boards** (field-service/enterprise):
  - *Microsoft D365 URS* — Schedule Board: resource list, timeline,
    an **unscheduled-requirements pane**, map view, drag-and-drop.
    ([learn.microsoft.com](https://learn.microsoft.com/en-us/dynamics365/common-scheduler/use-schedule-board))
  - *Salesforce Field Service* — Dispatcher/Scheduling Console: Gantt
    + service-appointment list + map + KPI bar.
    ([trailhead.salesforce.com](https://trailhead.salesforce.com/content/learn/modules/field-service-dispatcher-console-for-dispatchers/explore-the-dispatcher-console))
  - *Odoo Planning (EE)* — Gantt grouped by resource/role/project,
    plus separate **Open Shifts** and **My Planning** menus.
    ([odoo.com](https://www.odoo.com/app/planning-features))

Convergent secondary screens: an **open/unscheduled work** pane (our
Coverage menu ≈ D365's requirement pane ≈ Odoo's Open Shifts) and a
**person-centric** view (My Planning / employee mobile schedule).

### 5.1 Standard views

The base addon provides conventional list, form and calendar views for
assignments; `resource_planning_demand` adds the same for locations,
positions, schedules, services and requirements.

These views provide a dependable baseline for creating and inspecting
records without requiring an interactive planning component.

### 5.2 Matrix and roster grid

Evaluate OCA's `web_widget_x2many_2d_matrix` for compact
resource-by-time or resource-by-day displays.

Repository:
https://github.com/OCA/web/tree/19.0/web_widget_x2many_2d_matrix

The matrix widget is a potential building block, not a complete planning
workspace. Confirm whether its data and interaction model can represent
the required roster efficiently.

If a full planning grid is necessary, it should support:

- Resource rows.
- A configurable time horizon.
- Assignment indicators.
- Creation and editing of assignments.
- Navigation across days and weeks.
- Conflict and availability indicators.
- Clear visual differentiation between assigned work and unfilled demand.
- Rotation indicators showing the current pattern line or work/rest
  state where applicable.

A custom OWL grid should be introduced only if existing components cannot
satisfy these requirements.

### 5.3 Timeline

Evaluate OCA's `web_timeline` for displaying assignments and services
across a time axis.

Repository:
https://github.com/OCA/web/tree/19.0/web_timeline

A timeline is particularly useful for overlapping intervals, multi-day
assignments and visualising resource conflicts.

Do not assume that the generic timeline provides all planning
interactions. Verify drag-and-drop, resizing, resource grouping, editing
and validation against the target version.

If the timeline requires additional planning behaviour, implement that
behaviour through the shared server-side operations rather than
duplicating business rules in JavaScript.

Rotation cycles may be displayed as background bands or contextual
indicators, but the timeline must continue to represent actual
services and assignments as the authoritative planning records.

### 5.4 Dedicated coverage grid

The coverage grid is a separate planning perspective from the resource
roster.

It should allow planners to examine services, requirements, locations or
roles against time slots, showing:

- Required headcount or capacity.
- Assigned headcount or capacity.
- Remaining shortfall.
- Relevant conflicts or eligibility problems.
- Optional rotation-derived availability or work/rest status.

This view answers whether demand is adequately covered, whereas the
roster answers where each resource is allocated.

A specialised OWL client view may be justified if generic matrix
components cannot efficiently represent these calculations and
interactions.

### 5.5 DayPilot

DayPilot is an optional alternative for a richer interactive scheduler.

Evaluate it only if a working prototype demonstrates significant benefits
over the OCA-native approach.

Before adopting it, verify:

- Licensing compatibility with the intended OCA distribution.
- Which required capabilities are available under the chosen edition.
- Compatibility with Odoo's frontend architecture.
- Maintenance and upgrade costs.
- Whether the integration can be isolated in an optional addon.

It must not become a mandatory dependency of the core module.

### 5.6 Odoo 19.0 grid-view availability

Do not assume that a proposed or in-progress OCA grid-view addon is a
stable released dependency. Verify the current 19.0 branch, manifest,
tests, status and compatibility before selecting it.

The implementation should retain a fallback path using standard views
and the existing OCA components.

### 5.7 Shared planning operations

All planning interfaces must call the same server-side operations for
assignment creation, updates, conflict detection and coverage
calculation.

The domain operations must not depend on a particular view or frontend
library.

This provides consistent behaviour across forms, matrices, timelines and
future integrations.

## 6. Optional HR integration

The addon `resource_planning_hr` depends on
`resource_planning` and `hr`.

It may provide:

- Mapping between planning resources and employees.
- Employee-specific availability and leave integration.
- HR-specific qualifications or eligibility rules.
- Employee information for resource labels and grouping.
- Extensions to planning validation.

The core must not import HR models, require `hr.employee`, or assume
that all resources represent employees.

Generic resources must remain fully usable when the HR addon is not
installed.

## 7. Service generation and schedule changes

Recurring schedule generation must be safe and idempotent.

Repeated generation must not create duplicate services or duplicate
requirements.

Generation must preserve manually edited and published planning data
according to explicit rules. Changes to a schedule should not silently
overwrite assignments already made by a planner.

The implementation must define:

- The planning horizon used for generation.
- How generated records are identified.
- How schedule changes affect future services.
- How cancelled or obsolete services are handled.
- Which manual changes are preserved.
- How regeneration is reported to the user.

Rotation generation or application must follow the same principles. The
implementation must define:

- The horizon for calculating rotation states or generating
  rotation-derived records.
- How a resource or plan is anchored to a cycle.
- How duplicate suggestions or assignments are avoided.
- How exceptions and manual overrides are stored.
- How changes to a rotation template affect future, unpublished data.
- How published assignments and manually edited records are protected.
- Whether regeneration creates suggestions requiring confirmation or
  directly creates assignments.

These rules should be tested independently of the planning interface.

## 8. Security and extensibility

Apply Odoo access rights and record rules to all new models.

Ensure that:

- Access to planning records follows the intended organisational
  boundaries.
- State transitions and publication rules are enforced server-side.
- Assignment validation cannot be bypassed through imports, RPC or
  alternate views.
- Optional addons extend the core without introducing circular
  dependencies.
- External modules can extend eligibility, availability and conflict
  policies through stable extension points.
- Rotation templates, assignments and exceptions have appropriate access
  controls.
- Applying or regenerating a rotation cannot modify protected planning
  data without explicit permission.

## 9. Implementation plan

### Phase 1 — Core domain

Implement:

- [x] `resource.service.schedule`
- [x] `resource.position.slot`
- [x] `resource.service.requirement`
- [x] `resource.service.assignment`
- [x] `resource.role`
- [x] Standard list, form and calendar views
- [x] Interval integrity, assignment validation and conflict detection
- [x] Initial coverage calculations
- [x] Access rights and tests

*2026-10-25 — Phase 1 implemented in `resource_planning`
(OCA `resource` repo). Notes and deviations:*

- *Core depends on `resource` only — no `mail`, so no chatter yet.*
- *Recurrence is a simple pattern: daily or weekly, interval N,
  explicit `anchor_date`, weekday flags for weekly, per-schedule
  `horizon_days`. Generation is create-only and skips existing slots,
  so it is idempotent and never rewrites manual or published data.*
- *Schedule requirement defaults are `resource.service.requirement`
  rows with `schedule_id` set instead of a separate template model;
  a requirement has exactly one parent (service XOR schedule) and
  is validated in `create()`, which also covers RPC and imports.*
- *Conflict policy: half-open intervals; drafts stay tentative;
  `planned`/`published` hard-block overlaps against consuming
  assignments (`planned`/`published`/`completed`). Extension points:
  `_get_consuming_states`, `_get_blocking_states`,
  `_get_blocking_issues`, `_get_warning_issues`.*
- *Warnings (non-blocking): role mismatch against declared
  `resource.role_ids`, and work outside the resource's
  working calendar.*
- *Coverage is stored/computed: `required_qty`, `assigned_qty`,
  `open_qty` per service; `assigned_count`/`remaining_count` per
  requirement (counted over consuming assignments).*
- *Service publish/complete/cancel cascade to linked assignments.
  Published/completed services and published assignments cannot be
  deleted.*
- *No location model yet: the location abstraction is still
  undecided (the sibling `resource_reservation` uses `res.partner`);
  revisit before adding.*
- *Qualifications deferred: no suitable OCA abstraction confirmed;
  `resource.role` covers the initial use case.*

*2026-10-25 — locations, positions, periods and rotations added:*

- *Locations are `res.partner` records flagged `is_resource_location`
  (shared `resource_location` flag, also used by `resource_reservation`).*
- *`resource.service.position` is the post to fill inside a location.
  Each position carries its schedule and a list of dated rotation
  applications.*
- *`resource.service.period` is a named day period (Morning,
  Afternoon, Evening, Night ship as editable `noupdate` data). Times
  are position-specific and live on `resource.service.schedule.line`,
  which also carries the role and headcount stamped on generated
  services. A schedule without lines still generates one service per
  date from its default start/duration.*
- *Generated services keep `position_id`, `line_id`, `period_id` and
  a stored `location_id` for grouping; dedupe is per
  (schedule, position, line, start).*
- *`resource.service.rotation` is a matrix: `.row` (resource code,
  e.g. A, B, C) × cycle day → `.cell` mapping to a
  `resource.service.period`, including day-off periods
  (`period.is_day_off`). Periods carry a short `code` for matrix
  display. Default patterns ship as `noupdate` data, organized by
  `resource.service.rotation.tag`.*
- *Rotation assignment is dated: `resource.service.position.rotation`
  applies a plan to a position for a start/end range;
  `current_rotation_id` resolves the plan in effect. Rotation
  application to services/assignments is still Phase 5.*

*2026-10-26 — demand / planning / assignment split decided:*

- *The demand side — locations, positions, services, requirements,
  schedules — is extracted to `resource_planning_demand`. The base
  addon keeps only assignments: the interval model, conflict and
  availability validation, the roster engine, and the shared
  `resource.service.period` vocabulary. Demand link fields
  (`service_id`, `requirement_id`, `period_code`) are injected onto
  `resource.service.assignment` by the demand addon.*
- *`resource_planning_rotation` stays demand-free: positions become
  rotation hosts only in the `resource_planning_demand_rotation`
  glue addon, which also owns crew members.*
- *`resource_planning_position` dissolves into the demand addon and
  the glue addon.*

Verify existing OCA abstractions before creating qualification or
location models.

### Roadmap

#### Iteration 1 — Module split

- [x] Create `resource_planning_demand`: manifest, security, actions,
  menus.
- [x] Move the demand models: `resource.position.slot`,
  `resource.service.requirement`, `resource.service.schedule`,
  `resource.service.schedule.line`, `resource.service.position`,
  `res.partner.is_resource_location`.
- [x] Move the demand views: Services, Coverage, Schedules, Positions,
  Locations.
- [x] Inject `service_id`, `requirement_id`, `period_code` onto
  `resource.service.assignment` from the demand addon.
- [x] Move requirement-based coverage (`_coverage_by_day`) onto a
  demand-side `resource.service.roster` extension.
- [x] Create `resource_planning_demand_rotation`: position as rotation
  host, `application.position_id`, `member`, position rotation views.
- [x] Retire `resource_planning_position`; retarget
  `resource_planning_timeline` at `resource_planning_demand`.
- [x] Split `ir.model.access.csv`, groups, demo data and tests per
  addon; update `DESCRIPTION.md`/`USAGE.md`.

#### Iteration 2 — Planning interface spike

- [ ] Prototype a representative planning scenario on Odoo 19.0 with
  standard calendar and list views, `web_widget_x2many_2d_matrix` and
  `web_timeline`. Prior art (§5.0) converges on the roster grid —
  resources or positions as rows, days as columns — as the landing
  screen, with a coverage/open-work pane and a person-centric view as
  secondaries.
- [ ] Decide whether a custom OWL roster grid is justified.
- [ ] Evaluate DayPilot only if the OCA-native options are
  insufficient.

#### Iteration 3 — Operational planning

- [ ] Implement the selected planning interface in the optional
  `resource_planning_timeline` / `resource_planning_grid` addons.
- [ ] Coverage workflows: unfilled-requirements pane, bulk assignment.
- [ ] Daily roster status (§4.5): cross requirements, rotation plan,
  assigned resources and availability per cell.
- [ ] Keep all business rules in the base and demand addons — views
  call the same server-side operations.

#### Iteration 4 — Rotation application

- [ ] Derive dated assignments from rotation members × cells — the
  resource covering a crew code's day periods at a position.
- [ ] Crew-code links on assignments (`member_id` / `crew_id`).
- [ ] Explicit cycle anchoring; suggestions before automatic
  assignment.
- [ ] Exceptions, absences and manual overrides.
- [ ] Idempotent generation protecting published and manually edited
  planning data.

#### Iteration 5 — HR integration

- [ ] `resource_planning_hr`: employee mapping on `resource.resource`.
- [ ] HR-specific availability and eligibility (leave, contracts) as
  extension-point implementations.

#### Iteration 6 — Advanced planning

- [ ] Optimisation, richer capacity calculations and additional
  scheduling integrations, once the basic workflows are stable.

## 10. Acceptance criteria

The first release is acceptable when:

- The base addon installs without `hr`, without
  `resource_planning_demand` and without `resource_planning_rotation`.
- `resource_planning_rotation` installs and is usable without the
  demand addon.
- A generic resource can be assigned ad hoc in the base addon, and to
  a demand slot when `resource_planning_demand` is installed.
- Ad hoc assignments can be created without a recurring schedule.
- Dated services and staffing requirements exist independently of
  assignments.
- Unfilled requirements are visible and measurable.
- Assignment intervals are validated consistently.
- Overlapping assignments can be detected according to the configured
  policy.
- Core validation works independently of the planning view.
- Repeated service generation does not create duplicates.
- Manual and published planning data are protected from unintended
  regeneration.
- The selected Odoo 19.0 interface supports the initial planning
  workflow.
- The HR addon adds employee-specific functionality without making it a
  core requirement.
- Rotation templates, when enabled, are separate from schedules and
  assignments.
- At least a few popular rotation patterns are available as editable
  default data.
- Rotation application is anchored to an explicit date and timezone.
- Rotation-derived suggestions or assignments use the same conflict,
  availability and eligibility validation as ordinary assignments.
- Rotation regeneration is idempotent and does not overwrite protected
  planning data.
- All newly introduced persistent model names begin with `resource.`.

## 11. Decisions still to validate

Before implementation, confirm:

- The first operational domain and representative service-planning
  scenario.
- Whether requirements need multiple simultaneous roles or qualification
  combinations.
- Whether resource capacity can exceed one unit and how partial capacity
  should be represented.
- The precise conflict policy for different resource types.
- The result of the Odoo 19.0 matrix and timeline prototypes.
- Whether the coverage grid needs a dedicated OWL implementation.
- Which default rotation patterns are most relevant to the first
  operational domain.
- How crew-code assignments are derived from rotation members and
  cells: availability context, assignment suggestions or confirmed
  assignments, and how multi-day membership spans map to dated
  assignment intervals.
- How rotation exceptions, absences and manual overrides should be
  represented.
- Whether the 2-2-3 pattern requires separate day and night variants or
  a more general shift-sequence model.

The key architectural decision is fixed: planning is based on generic
resources, HR is an optional layer, and all new persistent models use the
`resource.` technical-name prefix. Rotation patterns are reusable
planning aids rather than prerequisites for ordinary scheduling. The
interface selection should follow a focused Odoo 19.0 prototype rather
than dictating the underlying data model.
