#!/usr/bin/env python
import argparse
import datetime
import os
import sys
import time

import sqlalchemy


DEFAULT_DB_URL = 'postgresql://postgres:123456@localhost'


def get_engine():
    return sqlalchemy.create_engine(
        os.environ.get('SQLALCHEMY_URL', DEFAULT_DB_URL),
        future=True,
    )


def parse_datetime(value):
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    else:
        parsed = parsed.astimezone(datetime.timezone.utc)
    return parsed


def parse_interval_hours(value):
    return datetime.timedelta(hours=float(value))


def print_row(row, prefix=''):
    for key in row.keys():
        print(f'{prefix}{key}={row[key]}')


def run_query(query, params=None):
    with get_engine().begin() as connection:
        return connection.execute(sqlalchemy.text(query), params or {})


def run_copy_range(args):
    row = run_query(
        "SELECT * FROM public.copy_siri_vehicle_location_range(:range_start, :range_end)",
        {
            'range_start': parse_datetime(args.range_start),
            'range_end': parse_datetime(args.range_end),
        }
    ).mappings().one()
    print_row(row)
    if args.fail_on_mismatch and not row['counts_match']:
        raise SystemExit(1)


def run_validate_range(args):
    row = run_query(
        "SELECT * FROM public.validate_siri_vehicle_location_range(:range_start, :range_end)",
        {
            'range_start': parse_datetime(args.range_start),
            'range_end': parse_datetime(args.range_end),
        }
    ).mappings().one()
    print_row(row)
    if args.fail_on_mismatch and not row['counts_match']:
        raise SystemExit(1)


def run_backfill(args):
    start = parse_datetime(args.range_start)
    end = parse_datetime(args.range_end)
    batch = parse_interval_hours(args.batch_hours)
    sleep_seconds = float(args.sleep_seconds)
    current = start

    while current < end:
        batch_end = min(current + batch, end)
        print(f'copying {current.isoformat()} -> {batch_end.isoformat()}')
        row = run_query(
            "SELECT * FROM public.copy_siri_vehicle_location_range(:range_start, :range_end)",
            {'range_start': current, 'range_end': batch_end}
        ).mappings().one()
        print_row(row, prefix='  ')
        if args.fail_on_mismatch and not row['counts_match']:
            raise SystemExit(1)
        current = batch_end
        if current < end and sleep_seconds > 0:
            time.sleep(sleep_seconds)


def run_status(_args):
    row = run_query("""
        SELECT
            to_regclass('public.siri_vehicle_location') AS live_table,
            to_regclass('public.siri_vehicle_location_timescaledb') AS shadow_table,
            to_regclass('public.siri_vehicle_location_old') AS rollback_table,
            EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'trg_sync_siri_vehicle_location_to_timescaledb'
                  AND tgrelid = 'public.siri_vehicle_location'::regclass
                  AND NOT tgisinternal
            ) AS sync_trigger_enabled
    """).mappings().one()
    print_row(row)


def run_cutover(_args):
    run_query("SELECT public.cutover_siri_vehicle_location_to_timescaledb()")
    print('cutover completed')


def run_rollback(_args):
    run_query("SELECT public.rollback_siri_vehicle_location_timescaledb_cutover()")
    print('rollback completed')


def run_create_lon_lat_indexes(_args):
    engine = get_engine()
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.execute(sqlalchemy.text("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_siri_vehicle_location_lat
            ON public.siri_vehicle_location (lat)
        """))
        connection.execute(sqlalchemy.text("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_siri_vehicle_location_lon
            ON public.siri_vehicle_location (lon)
        """))
    print('lon/lat indexes ensured')


def run_add_compression_policy(args):
    try:
        run_query("""
            ALTER TABLE public.siri_vehicle_location
            SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'siri_snapshot_id, siri_ride_stop_id',
                timescaledb.compress_orderby = 'recorded_at_time DESC, id DESC'
            )
        """)
        run_query("""
            SELECT add_compression_policy(
                'public.siri_vehicle_location',
                compress_after => CAST(:compress_after AS interval),
                if_not_exists => TRUE
            )
        """, {'compress_after': args.compress_after})
    except sqlalchemy.exc.DBAPIError as exc:
        raise SystemExit(
            "compression is not supported by the current TimescaleDB build/license; "
            "skip add-compression-policy or use a build that supports compression"
        ) from exc
    print(f'compression policy ensured: {args.compress_after}')


def build_parser():
    parser = argparse.ArgumentParser(
        description='Operate the siri_vehicle_location TimescaleDB migration.'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    copy_range = subparsers.add_parser('copy-range')
    copy_range.add_argument('--from', dest='range_start', required=True)
    copy_range.add_argument('--to', dest='range_end', required=True)
    copy_range.add_argument('--fail-on-mismatch', action='store_true')
    copy_range.set_defaults(func=run_copy_range)

    validate_range = subparsers.add_parser('validate-range')
    validate_range.add_argument('--from', dest='range_start', required=True)
    validate_range.add_argument('--to', dest='range_end', required=True)
    validate_range.add_argument('--fail-on-mismatch', action='store_true')
    validate_range.set_defaults(func=run_validate_range)

    backfill = subparsers.add_parser('backfill')
    backfill.add_argument('--from', dest='range_start', required=True)
    backfill.add_argument('--to', dest='range_end', required=True)
    backfill.add_argument('--batch-hours', default='24')
    backfill.add_argument('--sleep-seconds', default='0')
    backfill.add_argument('--fail-on-mismatch', action='store_true')
    backfill.set_defaults(func=run_backfill)

    status = subparsers.add_parser('status')
    status.set_defaults(func=run_status)

    cutover = subparsers.add_parser('cutover')
    cutover.set_defaults(func=run_cutover)

    rollback = subparsers.add_parser('rollback')
    rollback.set_defaults(func=run_rollback)

    create_lon_lat_indexes = subparsers.add_parser('create-lon-lat-indexes')
    create_lon_lat_indexes.set_defaults(func=run_create_lon_lat_indexes)

    add_compression_policy = subparsers.add_parser('add-compression-policy')
    add_compression_policy.add_argument('--compress-after', default='30 days')
    add_compression_policy.set_defaults(func=run_add_compression_policy)

    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
