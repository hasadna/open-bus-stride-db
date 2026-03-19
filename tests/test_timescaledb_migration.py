import os
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]


def upgrade_db():
    env = os.environ.copy()
    env["SQLALCHEMY_URL"] = "postgresql://postgres:123456@localhost"
    subprocess.check_call(
        [str(ROOT / ".venv" / "Scripts" / "alembic.exe"), "upgrade", "head"],
        cwd=str(ROOT),
        env=env,
    )


def test_timescaledb_shadow_table_and_trigger(get_db):
    upgrade_db()
    db = get_db(poolclass_nullpool=True)

    with db.get_session() as session:
        assert session.execute("SELECT extname FROM pg_extension WHERE extname='timescaledb'").scalar() == 'timescaledb'
        assert session.execute("""
            SELECT hypertable_name
            FROM timescaledb_information.hypertables
            WHERE hypertable_schema = 'public'
              AND hypertable_name = 'siri_vehicle_location_timescaledb'
        """).scalar() == 'siri_vehicle_location_timescaledb'
        session.execute("""
            INSERT INTO siri_vehicle_location (
                id, recorded_at_time, lon, lat, velocity
            ) VALUES (
                1, '2026-03-19 00:00:00', 34.0, 32.0, 12
            )
        """)
        session.commit()

    with db.get_session() as session:
        mirrored_row = session.execute("""
            SELECT id, velocity
            FROM siri_vehicle_location_timescaledb
            WHERE id = 1
        """).mappings().one()
        assert mirrored_row['id'] == 1
        assert mirrored_row['velocity'] == 12


def test_copy_validate_cutover_and_rollback(get_db):
    upgrade_db()
    db = get_db(poolclass_nullpool=True)

    with db.get_session() as session:
        session.execute("""
            INSERT INTO siri_vehicle_location (
                id, recorded_at_time, lon, lat, velocity
            ) VALUES (
                2, '2026-03-19 01:00:00', 34.1, 32.1, 20
            )
        """)
        session.execute("DELETE FROM siri_vehicle_location_timescaledb WHERE id = 2")
        session.commit()

    with db.get_session() as session:
        copied = session.execute("""
            SELECT * FROM public.copy_siri_vehicle_location_range(
                '2026-03-19 00:00:00',
                '2026-03-20 00:00:00'
            )
        """).mappings().one()
        validated = session.execute("""
            SELECT * FROM public.validate_siri_vehicle_location_range(
                '2026-03-19 00:00:00',
                '2026-03-20 00:00:00'
            )
        """).mappings().one()
        assert copied['inserted_count'] >= 1
        assert copied['counts_match'] is True
        assert validated['counts_match'] is True
        session.execute("SELECT public.cutover_siri_vehicle_location_to_timescaledb()")
        session.commit()

    with db.get_session() as session:
        assert session.execute("SELECT to_regclass('public.siri_vehicle_location_old')").scalar() == 'siri_vehicle_location_old'
        session.execute("""
            INSERT INTO siri_vehicle_location (
                id, recorded_at_time, lon, lat, velocity
            ) VALUES (
                3, '2026-03-19 02:00:00', 34.2, 32.2, 30
            )
        """)
        session.execute("""
            INSERT INTO siri_ride (id, first_vehicle_location_id, last_vehicle_location_id)
            VALUES (1, 3, 3)
        """)
        session.execute("""
            INSERT INTO siri_ride_stop (id, siri_ride_id, nearest_siri_vehicle_location_id)
            VALUES (1, 1, 3)
        """)
        session.commit()

    with db.get_session() as session:
        session.execute("SELECT public.rollback_siri_vehicle_location_timescaledb_cutover()")
        session.commit()

    with db.get_session() as session:
        assert session.execute("SELECT to_regclass('public.siri_vehicle_location_timescaledb')").scalar() == 'siri_vehicle_location_timescaledb'
        assert session.execute("SELECT 1 FROM siri_vehicle_location WHERE id = 2").scalar() == 1
        assert session.execute("SELECT COUNT(*) FROM siri_vehicle_location WHERE id = 3").scalar() == 0
        session.execute("""
            INSERT INTO siri_vehicle_location (
                id, recorded_at_time, lon, lat, velocity
            ) VALUES (
                4, '2026-03-19 03:00:00', 34.3, 32.3, 40
            )
        """)
        session.commit()
        assert session.execute("SELECT COUNT(*) FROM siri_vehicle_location_timescaledb WHERE id = 4").scalar() == 1
