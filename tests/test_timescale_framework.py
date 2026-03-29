from pathlib import Path

from open_bus_stride_db.timescale_framework import (
    OnlineHypertableMigrationOperator,
    OnlineHypertableMigrationSpec,
    SIRI_VEHICLE_LOCATION_SPEC,
)


def test_online_hypertable_spec_generates_default_names():
    spec = OnlineHypertableMigrationSpec(table_name='example_events')

    assert spec.shadow_table_name == 'example_events_timescaledb'
    assert spec.rollback_table_name == 'example_events_old'
    assert spec.sync_trigger_name == 'trg_sync_example_events_to_timescaledb'
    assert spec.copy_function_name == 'copy_example_events_range'
    assert spec.validate_function_name == 'validate_example_events_range'
    assert spec.cutover_function_name == 'cutover_example_events_to_timescaledb'
    assert spec.rollback_function_name == 'rollback_example_events_timescaledb_cutover'


def test_siri_vehicle_location_parser_supports_shared_and_legacy_index_commands():
    operator = OnlineHypertableMigrationOperator(SIRI_VEHICLE_LOCATION_SPEC)
    parser = operator.build_parser()

    create_indexes_args = parser.parse_args(['create-concurrent-indexes'])
    legacy_alias_args = parser.parse_args(['create-indexes'])

    assert create_indexes_args.func == operator.run_create_concurrent_indexes
    assert legacy_alias_args.func == operator.run_create_concurrent_indexes
def test_siri_vehicle_location_migration_syncs_updates_and_skips_null_timestamps():
    migration_sql = Path(
        'alembic/versions/b91a4af7e2c1_migrate_siri_vehicle_location_to_timescaledb.py'
    ).read_text()

    assert "AFTER INSERT OR UPDATE OR DELETE ON public.siri_vehicle_location" in migration_sql
    assert "IF NEW.recorded_at_time IS NULL THEN" in migration_sql
    assert "ON CONFLICT (recorded_at_time, id) DO UPDATE" in migration_sql
    assert "public.siri_vehicle_location still contains rows with NULL recorded_at_time" in migration_sql
