# TimescaleDB Candidate Reviews

These reviews are the current decision records for the next candidate tables
after `siri_vehicle_location`.

## Review Template

Each review must capture:

- candidacy score and rationale
- partition column
- chunk interval
- write pattern
- current PK/UNIQUE constraints
- inbound foreign keys
- outbound foreign keys
- migration mode
- post-cutover concurrent indexes
- compression settings
- retention policy
- aggregate policy
- blockers and recommendation

## Current Reviews

### `gtfs_ride_stop`

- Candidacy score: 6
- Recommendation: Assess only; do not approve Timescale migration yet.
- Rationale: Has time columns and inbound id-based references, but looks closer to daily refreshed schedule data than append-heavy telemetry.
- Partition column: `arrival_time`
- Chunk interval: `7 days` by default unless measured otherwise
- Write pattern: batch refresh / schedule reference data
- Current PK/UNIQUE constraints: `PRIMARY KEY (id)`
- Inbound foreign keys: `gtfs_ride.first_gtfs_ride_stop_id -> gtfs_ride_stop.id`; `gtfs_ride.last_gtfs_ride_stop_id -> gtfs_ride_stop.id`
- Outbound foreign keys: `gtfs_ride_stop.gtfs_stop_id -> gtfs_stop.id`; `gtfs_ride_stop.gtfs_ride_id -> gtfs_ride.id`
- Chosen migration mode: shadow cutover only if candidacy is proven later
- Post-cutover indexes: none
- Compression settings: defer until real query patterns justify migration
- Retention policy: not defined
- Aggregate policy: not defined
- Blockers: `id`-only inbound foreign keys from `gtfs_ride`; time-range query value and scale are not yet proven

### `siri_ride_stop`

- Candidacy score: 3 ⚠️
- Recommendation: Do not migrate unless a new immutable time dimension and query need are introduced.
- Rationale: Relational stop-order table with no natural immutable time partition key and no sign of append-heavy telemetry access.
- Partition column: none identified
- Chunk interval: not applicable
- Write pattern: relational / lookup-oriented
- Current PK/UNIQUE constraints: `PRIMARY KEY (id)`; `UNIQUE (siri_ride_id, siri_stop_id, order)`
- Inbound foreign keys: `siri_vehicle_location.siri_ride_stop_id -> siri_ride_stop.id`
- Outbound foreign keys: `siri_ride_stop.siri_stop_id -> siri_stop.id`; `siri_ride_stop.siri_ride_id -> siri_ride.id`; `siri_ride_stop.gtfs_stop_id -> gtfs_stop.id`; `siri_ride_stop.nearest_siri_vehicle_location_id -> siri_vehicle_location.id`
- Chosen migration mode: do not migrate in current schema
- Post-cutover indexes: none
- Compression settings: not applicable
- Retention policy: not defined
- Aggregate policy: not defined
- Blockers: no natural time or sequential partition column suitable for Timescale; table shape is relational rather than telemetry/event oriented
