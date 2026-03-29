"""prepare siri_vehicle_location timescaledb migration

Revision ID: b91a4af7e2c1
Revises: eb501cf9f471
Create Date: 2026-03-19 21:40:00.000000+00:00

"""
from textwrap import dedent

from alembic import op
import sqlalchemy as sa


revision = 'b91a4af7e2c1'
down_revision = 'eb501cf9f471'
branch_labels = None
depends_on = None

SHADOW_TABLE = 'siri_vehicle_location_timescaledb'
ROLLBACK_TABLE = 'siri_vehicle_location_old'
SYNC_TRIGGER = 'trg_sync_siri_vehicle_location_to_timescaledb'

COLUMNS = (
    'id',
    'siri_snapshot_id',
    'siri_ride_stop_id',
    'recorded_at_time',
    'lon',
    'lat',
    'bearing',
    'velocity',
    'distance_from_journey_start',
    'distance_from_siri_ride_stop_meters',
)


def _column_list(prefix=None):
    if prefix:
        return ",\n                ".join(f"{prefix}.{column}" for column in COLUMNS)
    return ", ".join(COLUMNS)


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        SHADOW_TABLE,
        sa.Column(
            'id', sa.BigInteger(),
            server_default=sa.text("nextval('siri_vehicle_location_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column('siri_snapshot_id', sa.Integer(), nullable=True),
        sa.Column('siri_ride_stop_id', sa.BigInteger(), nullable=True),
        sa.Column('recorded_at_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('bearing', sa.Integer(), nullable=True),
        sa.Column('velocity', sa.Integer(), nullable=True),
        sa.Column('distance_from_journey_start', sa.Integer(), nullable=True),
        sa.Column('distance_from_siri_ride_stop_meters', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['siri_snapshot_id'], ['siri_snapshot.id']),
        sa.ForeignKeyConstraint(['siri_ride_stop_id'], ['siri_ride_stop.id']),
    )
    op.create_index('ix_siri_vehicle_location_timescaledb_id', SHADOW_TABLE, ['id'], unique=False)
    op.create_index('ix_siri_vehicle_location_timescaledb_recorded_at_time', SHADOW_TABLE, ['recorded_at_time'], unique=False)
    op.create_index('uq_siri_vehicle_location_timescaledb_recorded_at_time_id', SHADOW_TABLE, ['recorded_at_time', 'id'], unique=True)
    op.create_index('ix_siri_vehicle_location_timescaledb_siri_snapshot_id', SHADOW_TABLE, ['siri_snapshot_id'], unique=False)
    op.create_index('ix_siri_vehicle_location_timescaledb_siri_ride_stop_id', SHADOW_TABLE, ['siri_ride_stop_id'], unique=False)

    op.execute(dedent("""
        SELECT create_hypertable(
            'public.siri_vehicle_location_timescaledb',
            'recorded_at_time',
            chunk_time_interval => INTERVAL '1 day',
            migrate_data => FALSE,
            if_not_exists => TRUE
        )
    """))

    statements = [
        dedent(f"""
            CREATE OR REPLACE FUNCTION public.sync_siri_vehicle_location_to_timescaledb()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    DELETE FROM public.{SHADOW_TABLE}
                    WHERE recorded_at_time = OLD.recorded_at_time
                      AND id = OLD.id;
                    RETURN OLD;
                END IF;

                IF TG_OP = 'UPDATE' AND OLD.recorded_at_time IS NOT NULL THEN
                    DELETE FROM public.{SHADOW_TABLE}
                    WHERE recorded_at_time = OLD.recorded_at_time
                      AND id = OLD.id;
                END IF;

                IF NEW.recorded_at_time IS NULL THEN
                    RETURN NEW;
                END IF;

                INSERT INTO public.{SHADOW_TABLE} (
                    {_column_list()}
                )
                VALUES (
                    {_column_list('NEW')}
                )
                ON CONFLICT (recorded_at_time, id) DO UPDATE
                SET siri_snapshot_id = EXCLUDED.siri_snapshot_id,
                    siri_ride_stop_id = EXCLUDED.siri_ride_stop_id,
                    lon = EXCLUDED.lon,
                    lat = EXCLUDED.lat,
                    bearing = EXCLUDED.bearing,
                    velocity = EXCLUDED.velocity,
                    distance_from_journey_start = EXCLUDED.distance_from_journey_start,
                    distance_from_siri_ride_stop_meters = EXCLUDED.distance_from_siri_ride_stop_meters;
                RETURN NEW;
            END;
            $$;
        """),
        dedent(f"""
            CREATE OR REPLACE FUNCTION public.enable_siri_vehicle_location_sync_trigger()
            RETURNS void
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgname = '{SYNC_TRIGGER}'
                      AND tgrelid = 'public.siri_vehicle_location'::regclass
                      AND NOT tgisinternal
                ) THEN
                    EXECUTE 'CREATE TRIGGER {SYNC_TRIGGER}
                             AFTER INSERT OR UPDATE OR DELETE ON public.siri_vehicle_location
                             FOR EACH ROW
                             EXECUTE FUNCTION public.sync_siri_vehicle_location_to_timescaledb()';
                END IF;
            END;
            $$;
        """),
        dedent(f"""
            CREATE OR REPLACE FUNCTION public.disable_siri_vehicle_location_sync_trigger()
            RETURNS void
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgname = '{SYNC_TRIGGER}'
                      AND tgrelid = 'public.siri_vehicle_location'::regclass
                      AND NOT tgisinternal
                ) THEN
                    EXECUTE 'DROP TRIGGER {SYNC_TRIGGER} ON public.siri_vehicle_location';
                END IF;
            END;
            $$;
        """),
        dedent("""
            CREATE OR REPLACE FUNCTION public.rename_index_if_exists(old_name text, new_name text)
            RETURNS void
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF to_regclass(format('public.%s', old_name)) IS NOT NULL
                AND to_regclass(format('public.%s', new_name)) IS NULL THEN
                    EXECUTE format('ALTER INDEX public.%I RENAME TO %I', old_name, new_name);
                END IF;
            END;
            $$;
        """),
        dedent("""
            CREATE OR REPLACE FUNCTION public.rename_constraint_if_exists(table_name regclass, old_name text, new_name text)
            RETURNS void
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conrelid = table_name
                      AND conname = old_name
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conrelid = table_name
                      AND conname = new_name
                ) THEN
                    EXECUTE format('ALTER TABLE %s RENAME CONSTRAINT %I TO %I', table_name, old_name, new_name);
                END IF;
            END;
            $$;
        """),
        dedent(f"""
            CREATE OR REPLACE FUNCTION public.copy_siri_vehicle_location_range(range_start timestamptz, range_end timestamptz)
            RETURNS TABLE (
                source_count bigint,
                inserted_count bigint,
                target_count bigint,
                source_min_recorded_at_time timestamptz,
                source_max_recorded_at_time timestamptz,
                target_min_recorded_at_time timestamptz,
                target_max_recorded_at_time timestamptz,
                counts_match boolean
            )
            LANGUAGE plpgsql
            AS $$
            DECLARE
                rows_inserted bigint;
            BEGIN
                INSERT INTO public.{SHADOW_TABLE} (
                    {_column_list()}
                )
                SELECT
                    {_column_list('source_row')}
                FROM public.siri_vehicle_location AS source_row
                WHERE source_row.recorded_at_time >= range_start
                  AND source_row.recorded_at_time < range_end
                ON CONFLICT (recorded_at_time, id) DO NOTHING;

                GET DIAGNOSTICS rows_inserted = ROW_COUNT;

                RETURN QUERY
                WITH source_stats AS (
                    SELECT
                        COUNT(*) AS source_count,
                        MIN(recorded_at_time)::timestamptz AS source_min_recorded_at_time,
                        MAX(recorded_at_time)::timestamptz AS source_max_recorded_at_time
                    FROM public.siri_vehicle_location
                    WHERE recorded_at_time >= range_start
                      AND recorded_at_time < range_end
                ),
                target_stats AS (
                    SELECT
                        COUNT(*) AS target_count,
                        MIN(recorded_at_time)::timestamptz AS target_min_recorded_at_time,
                        MAX(recorded_at_time)::timestamptz AS target_max_recorded_at_time
                    FROM public.{SHADOW_TABLE}
                    WHERE recorded_at_time >= range_start
                      AND recorded_at_time < range_end
                )
                SELECT
                    source_stats.source_count,
                    rows_inserted,
                    target_stats.target_count,
                    source_stats.source_min_recorded_at_time,
                    source_stats.source_max_recorded_at_time,
                    target_stats.target_min_recorded_at_time,
                    target_stats.target_max_recorded_at_time,
                    source_stats.source_count = target_stats.target_count
                FROM source_stats, target_stats;
            END;
            $$;
        """),
        dedent(f"""
            CREATE OR REPLACE FUNCTION public.validate_siri_vehicle_location_range(range_start timestamptz, range_end timestamptz)
            RETURNS TABLE (
                source_count bigint,
                target_count bigint,
                source_min_recorded_at_time timestamptz,
                source_max_recorded_at_time timestamptz,
                target_min_recorded_at_time timestamptz,
                target_max_recorded_at_time timestamptz,
                counts_match boolean
            )
            LANGUAGE sql
            AS $$
                WITH source_stats AS (
                    SELECT
                        COUNT(*) AS source_count,
                        MIN(recorded_at_time)::timestamptz AS source_min_recorded_at_time,
                        MAX(recorded_at_time)::timestamptz AS source_max_recorded_at_time
                    FROM public.siri_vehicle_location
                    WHERE recorded_at_time >= range_start
                      AND recorded_at_time < range_end
                ),
                target_stats AS (
                    SELECT
                        COUNT(*) AS target_count,
                        MIN(recorded_at_time)::timestamptz AS target_min_recorded_at_time,
                        MAX(recorded_at_time)::timestamptz AS target_max_recorded_at_time
                    FROM public.{SHADOW_TABLE}
                    WHERE recorded_at_time >= range_start
                      AND recorded_at_time < range_end
                )
                SELECT
                    source_stats.source_count,
                    target_stats.target_count,
                    source_stats.source_min_recorded_at_time,
                    source_stats.source_max_recorded_at_time,
                    target_stats.target_min_recorded_at_time,
                    target_stats.target_max_recorded_at_time,
                    source_stats.source_count = target_stats.target_count
                FROM source_stats, target_stats;
            $$;
        """),
    ]
    for statement in statements:
        op.execute(statement)

    op.execute(_cutover_function_sql())
    op.execute(_rollback_function_sql())
    op.execute("SELECT public.enable_siri_vehicle_location_sync_trigger()")


def downgrade():
    op.execute("SELECT public.disable_siri_vehicle_location_sync_trigger()")
    op.execute("DROP FUNCTION IF EXISTS public.rollback_siri_vehicle_location_timescaledb_cutover()")
    op.execute("DROP FUNCTION IF EXISTS public.cutover_siri_vehicle_location_to_timescaledb()")
    op.execute("DROP FUNCTION IF EXISTS public.validate_siri_vehicle_location_range(timestamptz, timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS public.validate_siri_vehicle_location_range(timestamp, timestamp)")
    op.execute("DROP FUNCTION IF EXISTS public.copy_siri_vehicle_location_range(timestamptz, timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS public.copy_siri_vehicle_location_range(timestamp, timestamp)")
    op.execute("DROP FUNCTION IF EXISTS public.rename_constraint_if_exists(regclass, text, text)")
    op.execute("DROP FUNCTION IF EXISTS public.rename_index_if_exists(text, text)")
    op.execute("DROP FUNCTION IF EXISTS public.disable_siri_vehicle_location_sync_trigger()")
    op.execute("DROP FUNCTION IF EXISTS public.enable_siri_vehicle_location_sync_trigger()")
    op.execute("DROP FUNCTION IF EXISTS public.sync_siri_vehicle_location_to_timescaledb()")
    op.drop_index('ix_siri_vehicle_location_timescaledb_siri_ride_stop_id', table_name=SHADOW_TABLE)
    op.drop_index('ix_siri_vehicle_location_timescaledb_siri_snapshot_id', table_name=SHADOW_TABLE)
    op.drop_index('uq_siri_vehicle_location_timescaledb_recorded_at_time_id', table_name=SHADOW_TABLE)
    op.drop_index('ix_siri_vehicle_location_timescaledb_recorded_at_time', table_name=SHADOW_TABLE)
    op.drop_index('ix_siri_vehicle_location_timescaledb_id', table_name=SHADOW_TABLE)
    op.drop_table(SHADOW_TABLE)


def _cutover_function_sql():
    return dedent(f"""
        CREATE OR REPLACE FUNCTION public.cutover_siri_vehicle_location_to_timescaledb()
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF to_regclass('public.siri_vehicle_location') IS NULL THEN
                RAISE EXCEPTION 'public.siri_vehicle_location is missing';
            END IF;
            IF to_regclass('public.{SHADOW_TABLE}') IS NULL THEN
                RAISE EXCEPTION 'public.{SHADOW_TABLE} is missing';
            END IF;
            IF to_regclass('public.{ROLLBACK_TABLE}') IS NOT NULL THEN
                RAISE EXCEPTION 'public.{ROLLBACK_TABLE} already exists';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM public.siri_vehicle_location
                WHERE recorded_at_time IS NULL
            ) THEN
                RAISE EXCEPTION 'public.siri_vehicle_location still contains rows with NULL recorded_at_time';
            END IF;

            LOCK TABLE public.siri_ride IN ACCESS EXCLUSIVE MODE;
            LOCK TABLE public.siri_ride_stop IN ACCESS EXCLUSIVE MODE;
            LOCK TABLE public.siri_vehicle_location IN ACCESS EXCLUSIVE MODE;
            LOCK TABLE public.{SHADOW_TABLE} IN ACCESS EXCLUSIVE MODE;

            ALTER TABLE public.siri_ride
                DROP CONSTRAINT IF EXISTS fk_siri_ride_first_vehicle_location_id_siri_vehicle_location,
                DROP CONSTRAINT IF EXISTS fk_siri_ride_last_vehicle_location_id_siri_vehicle_location;
            ALTER TABLE public.siri_ride_stop
                DROP CONSTRAINT IF EXISTS fk_siri_ride_stop_nearest_siri_vehicle_location_id_siri_vehicle_location;

            PERFORM public.disable_siri_vehicle_location_sync_trigger();

            ALTER TABLE public.siri_vehicle_location RENAME TO {ROLLBACK_TABLE};
            PERFORM public.rename_constraint_if_exists('public.{ROLLBACK_TABLE}'::regclass, 'pk_siri_vehicle_location', 'pk_{ROLLBACK_TABLE}');
            PERFORM public.rename_constraint_if_exists('public.{ROLLBACK_TABLE}'::regclass, 'fk_siri_vehicle_location_siri_snapshot_id_siri_snapshot', 'fk_{ROLLBACK_TABLE}_siri_snapshot_id_siri_snapshot');
            PERFORM public.rename_constraint_if_exists('public.{ROLLBACK_TABLE}'::regclass, 'fk_siri_vehicle_location_siri_ride_stop_id_siri_ride_stop', 'fk_{ROLLBACK_TABLE}_siri_ride_stop_id_siri_ride_stop');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_recorded_at_time', 'ix_{ROLLBACK_TABLE}_recorded_at_time');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_siri_snapshot_id', 'ix_{ROLLBACK_TABLE}_siri_snapshot_id');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_siri_ride_stop_id', 'ix_{ROLLBACK_TABLE}_siri_ride_stop_id');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_lat', 'ix_{ROLLBACK_TABLE}_lat');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_lon', 'ix_{ROLLBACK_TABLE}_lon');

            ALTER TABLE public.{SHADOW_TABLE} RENAME TO siri_vehicle_location;
            PERFORM public.rename_constraint_if_exists('public.siri_vehicle_location'::regclass, 'fk_{SHADOW_TABLE}_siri_snapshot_id_siri_snapshot', 'fk_siri_vehicle_location_siri_snapshot_id_siri_snapshot');
            PERFORM public.rename_constraint_if_exists('public.siri_vehicle_location'::regclass, 'fk_{SHADOW_TABLE}_siri_ride_stop_id_siri_ride_stop', 'fk_siri_vehicle_location_siri_ride_stop_id_siri_ride_stop');
            PERFORM public.rename_index_if_exists('ix_{SHADOW_TABLE}_id', 'ix_siri_vehicle_location_id');
            PERFORM public.rename_index_if_exists('ix_{SHADOW_TABLE}_recorded_at_time', 'ix_siri_vehicle_location_recorded_at_time');
            PERFORM public.rename_index_if_exists('uq_{SHADOW_TABLE}_recorded_at_time_id', 'uq_siri_vehicle_location_recorded_at_time_id');
            PERFORM public.rename_index_if_exists('ix_{SHADOW_TABLE}_siri_snapshot_id', 'ix_siri_vehicle_location_siri_snapshot_id');
            PERFORM public.rename_index_if_exists('ix_{SHADOW_TABLE}_siri_ride_stop_id', 'ix_siri_vehicle_location_siri_ride_stop_id');
            PERFORM public.rename_index_if_exists('ix_{SHADOW_TABLE}_lat', 'ix_siri_vehicle_location_lat');
            PERFORM public.rename_index_if_exists('ix_{SHADOW_TABLE}_lon', 'ix_siri_vehicle_location_lon');
        END;
        $$;
    """)


def _rollback_function_sql():
    return dedent(f"""
        CREATE OR REPLACE FUNCTION public.rollback_siri_vehicle_location_timescaledb_cutover()
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF to_regclass('public.{ROLLBACK_TABLE}') IS NULL THEN
                RAISE EXCEPTION 'public.{ROLLBACK_TABLE} is missing';
            END IF;
            IF to_regclass('public.{SHADOW_TABLE}') IS NOT NULL THEN
                RAISE EXCEPTION 'public.{SHADOW_TABLE} already exists';
            END IF;

            LOCK TABLE public.siri_ride IN ACCESS EXCLUSIVE MODE;
            LOCK TABLE public.siri_ride_stop IN ACCESS EXCLUSIVE MODE;
            LOCK TABLE public.siri_vehicle_location IN ACCESS EXCLUSIVE MODE;
            LOCK TABLE public.{ROLLBACK_TABLE} IN ACCESS EXCLUSIVE MODE;

            ALTER TABLE public.siri_ride
                DROP CONSTRAINT IF EXISTS fk_siri_ride_first_vehicle_location_id_siri_vehicle_location,
                DROP CONSTRAINT IF EXISTS fk_siri_ride_last_vehicle_location_id_siri_vehicle_location;
            ALTER TABLE public.siri_ride_stop
                DROP CONSTRAINT IF EXISTS fk_siri_ride_stop_nearest_siri_vehicle_location_id_siri_vehicle_location;

            ALTER TABLE public.siri_vehicle_location RENAME TO {SHADOW_TABLE};
            PERFORM public.rename_constraint_if_exists('public.{SHADOW_TABLE}'::regclass, 'fk_siri_vehicle_location_siri_snapshot_id_siri_snapshot', 'fk_{SHADOW_TABLE}_siri_snapshot_id_siri_snapshot');
            PERFORM public.rename_constraint_if_exists('public.{SHADOW_TABLE}'::regclass, 'fk_siri_vehicle_location_siri_ride_stop_id_siri_ride_stop', 'fk_{SHADOW_TABLE}_siri_ride_stop_id_siri_ride_stop');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_id', 'ix_{SHADOW_TABLE}_id');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_recorded_at_time', 'ix_{SHADOW_TABLE}_recorded_at_time');
            PERFORM public.rename_index_if_exists('uq_siri_vehicle_location_recorded_at_time_id', 'uq_{SHADOW_TABLE}_recorded_at_time_id');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_siri_snapshot_id', 'ix_{SHADOW_TABLE}_siri_snapshot_id');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_siri_ride_stop_id', 'ix_{SHADOW_TABLE}_siri_ride_stop_id');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_lat', 'ix_{SHADOW_TABLE}_lat');
            PERFORM public.rename_index_if_exists('ix_siri_vehicle_location_lon', 'ix_{SHADOW_TABLE}_lon');

            ALTER TABLE public.{ROLLBACK_TABLE} RENAME TO siri_vehicle_location;
            PERFORM public.rename_constraint_if_exists('public.siri_vehicle_location'::regclass, 'pk_{ROLLBACK_TABLE}', 'pk_siri_vehicle_location');
            PERFORM public.rename_constraint_if_exists('public.siri_vehicle_location'::regclass, 'fk_{ROLLBACK_TABLE}_siri_snapshot_id_siri_snapshot', 'fk_siri_vehicle_location_siri_snapshot_id_siri_snapshot');
            PERFORM public.rename_constraint_if_exists('public.siri_vehicle_location'::regclass, 'fk_{ROLLBACK_TABLE}_siri_ride_stop_id_siri_ride_stop', 'fk_siri_vehicle_location_siri_ride_stop_id_siri_ride_stop');
            PERFORM public.rename_index_if_exists('ix_{ROLLBACK_TABLE}_recorded_at_time', 'ix_siri_vehicle_location_recorded_at_time');
            PERFORM public.rename_index_if_exists('ix_{ROLLBACK_TABLE}_siri_snapshot_id', 'ix_siri_vehicle_location_siri_snapshot_id');
            PERFORM public.rename_index_if_exists('ix_{ROLLBACK_TABLE}_siri_ride_stop_id', 'ix_siri_vehicle_location_siri_ride_stop_id');
            PERFORM public.rename_index_if_exists('ix_{ROLLBACK_TABLE}_lat', 'ix_siri_vehicle_location_lat');
            PERFORM public.rename_index_if_exists('ix_{ROLLBACK_TABLE}_lon', 'ix_siri_vehicle_location_lon');

            ALTER TABLE public.siri_ride
                ADD CONSTRAINT fk_siri_ride_first_vehicle_location_id_siri_vehicle_location
                FOREIGN KEY (first_vehicle_location_id) REFERENCES public.siri_vehicle_location(id),
                ADD CONSTRAINT fk_siri_ride_last_vehicle_location_id_siri_vehicle_location
                FOREIGN KEY (last_vehicle_location_id) REFERENCES public.siri_vehicle_location(id);
            ALTER TABLE public.siri_ride_stop
                ADD CONSTRAINT fk_siri_ride_stop_nearest_siri_vehicle_location_id_siri_vehicle_location
                FOREIGN KEY (nearest_siri_vehicle_location_id) REFERENCES public.siri_vehicle_location(id);

            PERFORM public.enable_siri_vehicle_location_sync_trigger();
        END;
        $$;
    """)
