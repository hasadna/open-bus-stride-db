import argparse
import datetime
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Sequence, Tuple

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


@dataclass(frozen=True)
class ConcurrentIndexSpec:
    name: str
    columns: Tuple[str, ...]

    def create_sql(self, qualified_table_name):
        columns_sql = ', '.join(self.columns)
        return f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {self.name}
            ON {qualified_table_name} ({columns_sql})
        """


@dataclass(frozen=True)
class CompressionPolicySpec:
    segmentby: Tuple[str, ...]
    orderby: Tuple[str, ...]
    default_compress_after: str = '30 days'

    def alter_table_sql(self, qualified_table_name):
        return f"""
            ALTER TABLE {qualified_table_name}
            SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = '{", ".join(self.segmentby)}',
                timescaledb.compress_orderby = '{", ".join(self.orderby)}'
            )
        """

    def add_policy_sql(self, qualified_table_name):
        return f"""
            SELECT add_compression_policy(
                '{qualified_table_name}',
                compress_after => CAST(:compress_after AS interval),
                if_not_exists => TRUE
            )
        """


@dataclass(frozen=True)
class OnlineHypertableMigrationSpec:
    table_name: str
    schema_name: str = 'public'
    shadow_table_name: Optional[str] = None
    rollback_table_name: Optional[str] = None
    sync_trigger_name: Optional[str] = None
    sync_function_name: Optional[str] = None
    enable_trigger_function_name: Optional[str] = None
    disable_trigger_function_name: Optional[str] = None
    copy_function_name: Optional[str] = None
    validate_function_name: Optional[str] = None
    cutover_function_name: Optional[str] = None
    rollback_function_name: Optional[str] = None
    concurrent_indexes: Tuple[ConcurrentIndexSpec, ...] = ()
    compression_policy: Optional[CompressionPolicySpec] = None
    command_description: Optional[str] = None
    concurrent_indexes_command_name: str = 'create-concurrent-indexes'
    concurrent_indexes_command_aliases: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.shadow_table_name is None:
            object.__setattr__(self, 'shadow_table_name', '{}_timescaledb'.format(self.table_name))
        if self.rollback_table_name is None:
            object.__setattr__(self, 'rollback_table_name', '{}_old'.format(self.table_name))
        if self.sync_trigger_name is None:
            object.__setattr__(self, 'sync_trigger_name', 'trg_sync_{}_to_timescaledb'.format(self.table_name))
        if self.sync_function_name is None:
            object.__setattr__(self, 'sync_function_name', 'sync_{}_to_timescaledb'.format(self.table_name))
        if self.enable_trigger_function_name is None:
            object.__setattr__(self, 'enable_trigger_function_name', 'enable_{}_sync_trigger'.format(self.table_name))
        if self.disable_trigger_function_name is None:
            object.__setattr__(self, 'disable_trigger_function_name', 'disable_{}_sync_trigger'.format(self.table_name))
        if self.copy_function_name is None:
            object.__setattr__(self, 'copy_function_name', 'copy_{}_range'.format(self.table_name))
        if self.validate_function_name is None:
            object.__setattr__(self, 'validate_function_name', 'validate_{}_range'.format(self.table_name))
        if self.cutover_function_name is None:
            object.__setattr__(self, 'cutover_function_name', 'cutover_{}_to_timescaledb'.format(self.table_name))
        if self.rollback_function_name is None:
            object.__setattr__(self, 'rollback_function_name', 'rollback_{}_timescaledb_cutover'.format(self.table_name))
        if self.command_description is None:
            object.__setattr__(
                self,
                'command_description',
                'Operate the {} TimescaleDB migration.'.format(self.table_name),
            )

    @property
    def qualified_table_name(self):
        return '{}.{}'.format(self.schema_name, self.table_name)

    @property
    def qualified_shadow_table_name(self):
        return '{}.{}'.format(self.schema_name, self.shadow_table_name)

    @property
    def qualified_rollback_table_name(self):
        return '{}.{}'.format(self.schema_name, self.rollback_table_name)

    def qualified_function_name(self, function_name):
        return '{}.{}'.format(self.schema_name, function_name)

    def status_query(self):
        return """
            SELECT
                to_regclass(:live_table) AS live_table,
                to_regclass(:shadow_table) AS shadow_table,
                to_regclass(:rollback_table) AS rollback_table,
                EXISTS (
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgname = :sync_trigger_name
                      AND tgrelid = CAST(:live_table AS regclass)
                      AND NOT tgisinternal
                ) AS sync_trigger_enabled
        """

    def status_query_params(self):
        return {
            'live_table': self.qualified_table_name,
            'shadow_table': self.qualified_shadow_table_name,
            'rollback_table': self.qualified_rollback_table_name,
            'sync_trigger_name': self.sync_trigger_name,
        }


@dataclass(frozen=True)
class CandidateReview:
    table_name: str
    candidacy_score: int
    rationale: str
    partition_column: Optional[str]
    chunk_interval: str
    write_pattern: str
    current_constraints: Tuple[str, ...]
    inbound_foreign_keys: Tuple[str, ...]
    outbound_foreign_keys: Tuple[str, ...]
    migration_mode: str
    post_cutover_indexes: Tuple[str, ...]
    compression_settings: str
    retention_policy: Optional[str]
    aggregate_policy: Optional[str]
    recommendation: str
    blockers: Tuple[str, ...] = field(default_factory=tuple)


def candidate_review_to_markdown(review):
    lines = [
        '### `{}`'.format(review.table_name),
        '',
        '- Candidacy score: {}'.format(review.candidacy_score),
        '- Recommendation: {}'.format(review.recommendation),
        '- Rationale: {}'.format(review.rationale),
        '- Partition column: {}'.format(review.partition_column or 'none identified'),
        '- Chunk interval: {}'.format(review.chunk_interval),
        '- Write pattern: {}'.format(review.write_pattern),
        '- Current PK/UNIQUE constraints: {}'.format('; '.join(review.current_constraints) or 'none documented'),
        '- Inbound foreign keys: {}'.format('; '.join(review.inbound_foreign_keys) or 'none'),
        '- Outbound foreign keys: {}'.format('; '.join(review.outbound_foreign_keys) or 'none'),
        '- Chosen migration mode: {}'.format(review.migration_mode),
        '- Post-cutover indexes: {}'.format(', '.join(review.post_cutover_indexes) or 'none'),
        '- Compression settings: {}'.format(review.compression_settings),
        '- Retention policy: {}'.format(review.retention_policy or 'not defined'),
        '- Aggregate policy: {}'.format(review.aggregate_policy or 'not defined'),
    ]
    if review.blockers:
        lines.append('- Blockers: {}'.format('; '.join(review.blockers)))
    lines.append('')
    return '\n'.join(lines)


class OnlineHypertableMigrationOperator:
    def __init__(self, spec):
        self.spec = spec

    def run_query(self, query, params=None):
        with get_engine().begin() as connection:
            return connection.execute(sqlalchemy.text(query), params or {})

    def run_copy_range(self, args):
        row = self.run_query(
            "SELECT * FROM {}(:range_start, :range_end)".format(
                self.spec.qualified_function_name(self.spec.copy_function_name)
            ),
            {
                'range_start': parse_datetime(args.range_start),
                'range_end': parse_datetime(args.range_end),
            }
        ).mappings().one()
        print_row(row)
        if args.fail_on_mismatch and not row['counts_match']:
            raise SystemExit(1)

    def run_validate_range(self, args):
        row = self.run_query(
            "SELECT * FROM {}(:range_start, :range_end)".format(
                self.spec.qualified_function_name(self.spec.validate_function_name)
            ),
            {
                'range_start': parse_datetime(args.range_start),
                'range_end': parse_datetime(args.range_end),
            }
        ).mappings().one()
        print_row(row)
        if args.fail_on_mismatch and not row['counts_match']:
            raise SystemExit(1)

    def run_backfill(self, args):
        start = parse_datetime(args.range_start)
        end = parse_datetime(args.range_end)
        batch = parse_interval_hours(args.batch_hours)
        sleep_seconds = float(args.sleep_seconds)
        current = start

        while current < end:
            batch_end = min(current + batch, end)
            print('copying {} -> {}'.format(current.isoformat(), batch_end.isoformat()))
            row = self.run_query(
                "SELECT * FROM {}(:range_start, :range_end)".format(
                    self.spec.qualified_function_name(self.spec.copy_function_name)
                ),
                {'range_start': current, 'range_end': batch_end}
            ).mappings().one()
            print_row(row, prefix='  ')
            if args.fail_on_mismatch and not row['counts_match']:
                raise SystemExit(1)
            current = batch_end
            if current < end and sleep_seconds > 0:
                time.sleep(sleep_seconds)

    def run_status(self, _args):
        row = self.run_query(
            self.spec.status_query(),
            self.spec.status_query_params(),
        ).mappings().one()
        print_row(row)

    def run_cutover(self, _args):
        self.run_query(
            "SELECT {}()".format(
                self.spec.qualified_function_name(self.spec.cutover_function_name)
            )
        )
        print('cutover completed')

    def run_rollback(self, _args):
        self.run_query(
            "SELECT {}()".format(
                self.spec.qualified_function_name(self.spec.rollback_function_name)
            )
        )
        print('rollback completed')

    def run_create_concurrent_indexes(self, _args):
        if not self.spec.concurrent_indexes:
            print('no concurrent indexes configured')
            return
        engine = get_engine()
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            for index_spec in self.spec.concurrent_indexes:
                connection.execute(sqlalchemy.text(
                    index_spec.create_sql(self.spec.qualified_table_name)
                ))
        print('concurrent indexes ensured')

    def run_add_compression_policy(self, args):
        if self.spec.compression_policy is None:
            raise SystemExit('compression policy is not configured for {}'.format(self.spec.table_name))
        try:
            self.run_query(
                self.spec.compression_policy.alter_table_sql(self.spec.qualified_table_name)
            )
            self.run_query(
                self.spec.compression_policy.add_policy_sql(self.spec.qualified_table_name),
                {'compress_after': args.compress_after}
            )
        except sqlalchemy.exc.DBAPIError as exc:
            raise SystemExit(
                'compression is not supported by the current TimescaleDB build/license; '
                'skip add-compression-policy or use a build that supports compression'
            ) from exc
        print('compression policy ensured: {}'.format(args.compress_after))

    def build_parser(self):
        parser = argparse.ArgumentParser(description=self.spec.command_description)
        subparsers = parser.add_subparsers(dest='command', required=True)

        copy_range = subparsers.add_parser('copy-range')
        copy_range.add_argument('--from', dest='range_start', required=True)
        copy_range.add_argument('--to', dest='range_end', required=True)
        copy_range.add_argument('--fail-on-mismatch', action='store_true')
        copy_range.set_defaults(func=self.run_copy_range)

        validate_range = subparsers.add_parser('validate-range')
        validate_range.add_argument('--from', dest='range_start', required=True)
        validate_range.add_argument('--to', dest='range_end', required=True)
        validate_range.add_argument('--fail-on-mismatch', action='store_true')
        validate_range.set_defaults(func=self.run_validate_range)

        backfill = subparsers.add_parser('backfill')
        backfill.add_argument('--from', dest='range_start', required=True)
        backfill.add_argument('--to', dest='range_end', required=True)
        backfill.add_argument('--batch-hours', default='24')
        backfill.add_argument('--sleep-seconds', default='0')
        backfill.add_argument('--fail-on-mismatch', action='store_true')
        backfill.set_defaults(func=self.run_backfill)

        status = subparsers.add_parser('status')
        status.set_defaults(func=self.run_status)

        cutover = subparsers.add_parser('cutover')
        cutover.set_defaults(func=self.run_cutover)

        rollback = subparsers.add_parser('rollback')
        rollback.set_defaults(func=self.run_rollback)

        concurrent_indexes = subparsers.add_parser(
            self.spec.concurrent_indexes_command_name,
            aliases=list(self.spec.concurrent_indexes_command_aliases),
        )
        concurrent_indexes.set_defaults(func=self.run_create_concurrent_indexes)

        add_compression_policy = subparsers.add_parser('add-compression-policy')
        default_compress_after = (
            self.spec.compression_policy.default_compress_after
            if self.spec.compression_policy is not None else
            '30 days'
        )
        add_compression_policy.add_argument(
            '--compress-after',
            default=default_compress_after,
        )
        add_compression_policy.set_defaults(func=self.run_add_compression_policy)

        return parser

    def main(self, argv=None):
        args = self.build_parser().parse_args(argv)
        args.func(args)
        return 0


def build_candidate_reviews():
    return (
        CandidateReview(
            table_name='gtfs_ride_stop',
            candidacy_score=6,
            rationale=(
                'Has time columns and inbound id-based references, but looks closer to '
                'daily refreshed schedule data than append-heavy telemetry.'
            ),
            partition_column='arrival_time',
            chunk_interval='7 days by default unless measured otherwise',
            write_pattern='batch refresh / schedule reference data',
            current_constraints=(
                'PRIMARY KEY (id)',
            ),
            inbound_foreign_keys=(
                'gtfs_ride.first_gtfs_ride_stop_id -> gtfs_ride_stop.id',
                'gtfs_ride.last_gtfs_ride_stop_id -> gtfs_ride_stop.id',
            ),
            outbound_foreign_keys=(
                'gtfs_ride_stop.gtfs_stop_id -> gtfs_stop.id',
                'gtfs_ride_stop.gtfs_ride_id -> gtfs_ride.id',
            ),
            migration_mode='shadow cutover only if candidacy is proven later',
            post_cutover_indexes=(),
            compression_settings='defer until real query patterns justify migration',
            retention_policy=None,
            aggregate_policy=None,
            recommendation='Assess only; do not approve Timescale migration yet.',
            blockers=(
                'id-only inbound foreign keys from gtfs_ride',
                'time-range query value and scale are not yet proven',
            ),
        ),
        CandidateReview(
            table_name='siri_ride_stop',
            candidacy_score=3,
            rationale=(
                'Relational stop-order table with no natural immutable time partition key '
                'and no sign of append-heavy telemetry access.'
            ),
            partition_column=None,
            chunk_interval='not applicable',
            write_pattern='relational / lookup-oriented',
            current_constraints=(
                'PRIMARY KEY (id)',
                'UNIQUE (siri_ride_id, siri_stop_id, order)',
            ),
            inbound_foreign_keys=(
                'siri_vehicle_location.siri_ride_stop_id -> siri_ride_stop.id',
            ),
            outbound_foreign_keys=(
                'siri_ride_stop.siri_stop_id -> siri_stop.id',
                'siri_ride_stop.siri_ride_id -> siri_ride.id',
                'siri_ride_stop.gtfs_stop_id -> gtfs_stop.id',
                'siri_ride_stop.nearest_siri_vehicle_location_id -> siri_vehicle_location.id',
            ),
            migration_mode='do not migrate in current schema',
            post_cutover_indexes=(),
            compression_settings='not applicable',
            retention_policy=None,
            aggregate_policy=None,
            recommendation='Do not migrate unless a new immutable time dimension and query need are introduced.',
            blockers=(
                'no natural time or sequential partition column suitable for Timescale',
                'table shape is relational rather than telemetry/event oriented',
            ),
        ),
    )


SIRI_VEHICLE_LOCATION_SPEC = OnlineHypertableMigrationSpec(
    table_name='siri_vehicle_location',
    concurrent_indexes=(
        ConcurrentIndexSpec(name='ix_siri_vehicle_location_lat', columns=('lat',)),
        ConcurrentIndexSpec(name='ix_siri_vehicle_location_lon', columns=('lon',)),
    ),
    compression_policy=CompressionPolicySpec(
        segmentby=('siri_snapshot_id', 'siri_ride_stop_id'),
        orderby=('recorded_at_time DESC', 'id DESC'),
    ),
    concurrent_indexes_command_aliases=('create-lon-lat-indexes',),
)
