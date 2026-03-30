# TimescaleDB Migration Runbook

This branch adds an online migration path for `public.siri_vehicle_location` from a regular PostgreSQL table to a TimescaleDB hypertable.

The migration has three parts:

1. Apply the Alembic revision that creates the shadow hypertable and helper functions.
2. Backfill historical data into the shadow table while a trigger keeps new writes in sync.
3. Cut over with a short lock, then verify and optionally add compression and retention.

## What Changed

The branch adds these migration-specific pieces:

- `alembic/versions/b91a4af7e2c1_migrate_siri_vehicle_location_to_timescaledb.py`
  Creates `siri_vehicle_location_timescaledb`, enables the TimescaleDB extension, creates helper SQL functions, and installs a sync trigger on the live table.
- `open_bus_stride_db/timescale_framework.py`
  Adds a reusable operator for backfill, validation, cutover, rollback, concurrent indexes, and compression-policy setup.
- `bin/siri_vehicle_location_timescaledb_migration.py`
  CLI entrypoint for operating this migration.
- `tests/test_timescale_framework.py`
  Covers the operator parser and key migration SQL guarantees.
- `tests/conftest.py`, `Dockerfile`, `backup/Dockerfile`, `.github/workflows/ci.yml`
  Switch local and CI environments to PostgreSQL 14 with the `timescale/timescaledb:2.19.3-pg14-oss` image and PostgreSQL 14 client tools.

## Preconditions

Before you run this migration:

- Use PostgreSQL 14.
- Use a TimescaleDB image or installation that supports `CREATE EXTENSION timescaledb`.
- Make sure the application can tolerate a short write pause during cutover.
- Make sure you can connect with `SQLALCHEMY_URL`.
- Run the migration only after the code from this branch is deployed.

If you use local Docker, the repo now expects:

```bash
docker run -e POSTGRES_PASSWORD=123456 -p 5432:5432 -d timescale/timescaledb:2.19.3-pg14-oss
```

## Phase 1: Prepare the Database

Apply the Alembic revision:

```bash
. .env && alembic upgrade head
```

This creates:

- `public.siri_vehicle_location_timescaledb`
- `public.sync_siri_vehicle_location_to_timescaledb()`
- `public.enable_siri_vehicle_location_sync_trigger()`
- `public.disable_siri_vehicle_location_sync_trigger()`
- `public.copy_siri_vehicle_location_range(...)`
- `public.validate_siri_vehicle_location_range(...)`
- `public.cutover_siri_vehicle_location_to_timescaledb()`
- `public.rollback_siri_vehicle_location_timescaledb_cutover()`

The revision also enables a row-level trigger on `public.siri_vehicle_location` so inserts, updates, and deletes are mirrored into the shadow hypertable.

Check status:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py status
```

Expected state before backfill:

- `live_table=public.siri_vehicle_location`
- `shadow_table=public.siri_vehicle_location_timescaledb`
- `rollback_table=NULL`
- `sync_trigger_enabled=True`

## Phase 2: Backfill Historical Data

Backfill in bounded time ranges. The migration code copies rows by `recorded_at_time`, and the sync trigger keeps recent writes aligned while the backfill runs.

Example: backfill one month in 2 hour batches.

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py backfill \
  --from 2026-02-01T00:00:00+00:00 \
  --to 2026-03-01T00:00:00+00:00 \
  --batch-hours 2 \
  --fail-on-mismatch
```

Useful commands:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py copy-range \
  --from 2026-03-01T00:00:00+00:00 \
  --to 2026-03-02T00:00:00+00:00 \
  --fail-on-mismatch

. .env && python bin/siri_vehicle_location_timescaledb_migration.py validate-range \
  --from 2026-03-01T00:00:00+00:00 \
  --to 2026-03-02T00:00:00+00:00 \
  --fail-on-mismatch
```

Notes:

- Timestamps without a timezone are treated as UTC by the operator.
- `copy-range` is idempotent because inserts use `ON CONFLICT (recorded_at_time, id) DO NOTHING`.
- Updates and deletes on the live table are mirrored by the trigger.
- Rows with `NULL recorded_at_time` are skipped by the trigger and will block cutover later.

## Phase 3: Validate Before Cutover

Validate the full migration window before cutover. Run it by ranges if the table is large.

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py validate-range \
  --from 2026-02-01T00:00:00+00:00 \
  --to 2026-03-28T00:00:00+00:00 \
  --fail-on-mismatch
```

Then check for invalid rows in the live table:

```sql
SELECT COUNT(*)
FROM public.siri_vehicle_location
WHERE recorded_at_time IS NULL;
```

Cutover will fail if that count is not zero.

## Phase 4: Cut Over

The cutover function takes `ACCESS EXCLUSIVE` locks on:

- `public.siri_ride`
- `public.siri_ride_stop`
- `public.siri_vehicle_location`
- `public.siri_vehicle_location_timescaledb`

It then:

1. Drops foreign keys from `siri_ride` and `siri_ride_stop` that point to the live table.
2. Disables the sync trigger.
3. Renames `public.siri_vehicle_location` to `public.siri_vehicle_location_old`.
4. Renames `public.siri_vehicle_location_timescaledb` to `public.siri_vehicle_location`.
5. Renames indexes and constraints to the original names.

Run cutover:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py cutover
```

Expected state after cutover:

- `live_table=public.siri_vehicle_location`
- `shadow_table=NULL`
- `rollback_table=public.siri_vehicle_location_old`
- `sync_trigger_enabled=False`

Check it:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py status
```

## Phase 5: Post-Cutover Tasks

Create the lon/lat indexes concurrently after cutover:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py create-concurrent-indexes
```

The old command name still works:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py create-indexes
```

Optionally add compression:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py add-compression-policy
```

Default compression settings from the code:

- `segmentby = siri_snapshot_id`
- `orderby = recorded_at_time DESC, siri_ride_stop_id, id DESC`
- `compress_after = 30 days`

If the current TimescaleDB build does not support compression, the command exits with a clear error. In that case, skip compression or use a build that supports it.

If you have a defined raw-data retention window, add retention explicitly:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py add-retention-policy \
  --drop-after '365 days'
```

Do not guess the retention interval. Pick it from product or operations requirements.

## Rollback

If cutover completed and you need to revert:

```bash
. .env && python bin/siri_vehicle_location_timescaledb_migration.py rollback
```

Rollback does the reverse rename, restores the original foreign keys, and re-enables the sync trigger.

Expected state after rollback:

- `live_table=public.siri_vehicle_location`
- `shadow_table=public.siri_vehicle_location_timescaledb`
- `rollback_table=NULL`
- `sync_trigger_enabled=True`

## Operational Checklist

Use this sequence in production:

1. Deploy this branch's code.
2. Run `alembic upgrade head`.
3. Confirm `status`.
4. Backfill historical data in time ranges.
5. Run `validate-range` on the full target window.
6. Confirm there are no `NULL recorded_at_time` rows left in `public.siri_vehicle_location`.
7. Pause or reduce writers if needed.
8. Run `cutover`.
9. Confirm `status`.
10. Create concurrent lon/lat indexes.
11. Optionally add the compression policy.
12. Optionally add a retention policy if you have a defined raw-data window.
13. Keep `public.siri_vehicle_location_old` until you are satisfied with the migration.

## Failure Modes To Watch

- `CREATE EXTENSION timescaledb` fails:
  The database is not running with TimescaleDB installed.
- `cutover` fails on `NULL recorded_at_time`:
  Clean or delete those rows first.
- `validate-range` reports `counts_match=False`:
  Re-run `copy-range` or `backfill` for the affected window before cutover.
- `add-compression-policy` fails:
  The TimescaleDB build or license does not support compression.
- Queries or code still depend on foreign keys to `siri_vehicle_location(id)`:
  The hypertable enforces uniqueness on `(recorded_at_time, id)`, not on `id` alone. The migration preserves application-level access to the data, but a full FK-safe redesign still needs a follow-up schema decision.

## Related Files

- `alembic/versions/b91a4af7e2c1_migrate_siri_vehicle_location_to_timescaledb.py`
- `open_bus_stride_db/timescale_framework.py`
- `bin/siri_vehicle_location_timescaledb_migration.py`
