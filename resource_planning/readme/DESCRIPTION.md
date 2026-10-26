Assign generic resources to time intervals — the base addon of the
resource planning family, with no `hr` dependency.

- **Assignments** allocate a `resource.resource` to an explicit
  `[start, end)` interval, with a lifecycle (draft → planned →
  published → completed / cancelled).
- **Day periods** (`resource.service.period`) name the day's slots —
  Morning, Evening, Night — shared vocabulary used by demand
  schedules and rotation matrices.
- **Roles** (from `resource_role`) declare what a resource can
  fulfil; mismatches surface as warnings.

Overlapping assignments on the same resource are hard conflicts once
planned or published, while role mismatches and out-of-calendar work
surface as warnings. Availability, eligibility and conflict policies
are extension points.

Ad hoc assignments work standalone. The demand side — locations,
positions, dated slots and requirements — is added by
`resource_planning_demand`; rotations by `resource_planning_rotation`
and its `resource_planning_demand_rotation` glue; HR-specific rules
belong in the optional `resource_planning_hr` addon.
