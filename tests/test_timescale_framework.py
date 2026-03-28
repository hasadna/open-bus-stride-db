from open_bus_stride_db.timescale_framework import (
    OnlineHypertableMigrationOperator,
    OnlineHypertableMigrationSpec,
    SIRI_VEHICLE_LOCATION_SPEC,
    build_candidate_reviews,
    candidate_review_to_markdown,
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
    legacy_alias_args = parser.parse_args(['create-lon-lat-indexes'])

    assert create_indexes_args.func == operator.run_create_concurrent_indexes
    assert legacy_alias_args.func == operator.run_create_concurrent_indexes


def test_candidate_reviews_capture_expected_blockers():
    reviews = {review.table_name: review for review in build_candidate_reviews()}

    assert set(reviews) == {'gtfs_ride_stop', 'siri_ride_stop'}
    assert reviews['gtfs_ride_stop'].partition_column == 'arrival_time'
    assert 'id-only inbound foreign keys from gtfs_ride' in reviews['gtfs_ride_stop'].blockers
    assert reviews['siri_ride_stop'].partition_column is None
    assert 'no natural time or sequential partition column suitable for Timescale' in reviews['siri_ride_stop'].blockers


def test_candidate_review_markdown_includes_contract_fields():
    review = build_candidate_reviews()[0]
    markdown = candidate_review_to_markdown(review)

    assert 'Candidacy score' in markdown
    assert 'Inbound foreign keys' in markdown
    assert 'Chosen migration mode' in markdown
