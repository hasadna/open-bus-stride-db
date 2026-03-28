# TimescaleDB Online Migration Framework

This repository standardizes online TimescaleDB migrations around the existing
`siri_vehicle_location` workflow.

## Default Pattern

Use this sequence for tables that are strong hypertable candidates but cannot be
converted in place without breaking current `id`-based application contracts:

1. Review the table as a candidate first.
2. Create a shadow hypertable with compatible business columns and indexes.
3. Add a sync trigger so new inserts flow from the live table to the shadow table.
4. Backfill historical data in validated time windows.
5. Cut over by swapping the shadow table into production.
6. Keep a rollback table and rollback function available.
7. Rebuild optional concurrent indexes after cutover.
8. Add compression only when supported and justified.

## Decision Record Contract

Every future Timescale migration should start with a written decision record.
Document only the constraints, operating assumptions, and follow-up work that
the migration actually needs.

## Migration Mode Rules

- Prefer `TIMESTAMPTZ` event columns as partition columns.
- Default chunk interval to `7 days` unless measured workload or prior operational
  knowledge justifies something else.
- Do not invent retention or continuous aggregates without a stated requirement.
- Do not force PK/FK redesign by default. If a table has incompatible `id`-only
  constraints or foreign keys, prefer the shadow-cutover path.
- If a table lacks a natural time or sequential partition key, reject Timescale
  migration until the schema and access pattern justify it.

## Reusable Python Interface

The reusable implementation lives in `open_bus_stride_db.timescale_framework`.

Primary pieces:

- `OnlineHypertableMigrationSpec`: table-specific metadata and generated names
- `OnlineHypertableMigrationOperator`: shared CLI behavior for status, backfill,
  validation, cutover, rollback, concurrent-index rebuilds, and compression setup

`bin/siri_vehicle_location_timescaledb_migration.py` is the canonical example of
the operator-script pattern. Future table-specific scripts should stay thin and
only provide a spec object.
