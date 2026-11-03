import os
import unittest
from unittest.mock import patch

from sqlalchemy import text

from open_bus_stride_db import clickhouse
from open_bus_stride_db.clickhouse.models import Base, SiriVehicleLocation


class ClickHouseSessionTests(unittest.TestCase):
    @patch("open_bus_stride_db.clickhouse.create_engine")
    def test_connection_configuration(self, create_engine):
        with patch.dict(
            os.environ,
            {
                "CLICKHOUSE_URL": "https://example.test:8443",
                "CLICKHOUSE_USER": "user",
                "CLICKHOUSE_PASSWORD": "p@ss:word",
                "CLICKHOUSE_DATABASE": "transit",
            },
            clear=True,
        ):
            clickhouse.create_clickhouse_engine()
        url = create_engine.call_args.args[0]
        self.assertEqual(
            (url.host, url.port, url.database), ("example.test", 8443, "transit")
        )
        self.assertEqual((url.username, url.password), ("user", "p@ss:word"))
        self.assertEqual(url.query["protocol"], "https")

    def test_invalid_url(self):
        with patch.dict(os.environ, {"CLICKHOUSE_URL": "ftp://example.test"}, clear=True):
            with self.assertRaises(ValueError):
                clickhouse.create_clickhouse_engine()

    @patch("open_bus_stride_db.clickhouse.sessionmaker")
    @patch("open_bus_stride_db.clickhouse.create_clickhouse_engine")
    def test_session_cleanup_on_error(self, create_engine, sessionmaker):
        engine = create_engine.return_value
        session = sessionmaker.return_value.return_value
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with clickhouse.get_session() as actual:
                self.assertIs(actual, session)
                raise RuntimeError("failure")
        session.close.assert_called_once_with()
        engine.dispose.assert_called_once_with()

    def test_vehicle_location_mapping(self):
        table = Base.metadata.tables["siri_vehicle_location"]
        self.assertIs(SiriVehicleLocation.__table__, table)
        self.assertIn("recorded_at_time", table.c)
        self.assertIn("siri_ride_id", table.c)


@unittest.skipUnless(
    os.getenv("CLICKHOUSE_INTEGRATION_TEST") == "1",
    "Set CLICKHOUSE_INTEGRATION_TEST=1 for a live ClickHouse test",
)
class ClickHouseIntegrationTests(unittest.TestCase):
    def test_schema_query(self):
        with clickhouse.get_session() as session:
            self.assertEqual(session.execute(text("SELECT 1")).scalar(), 1)
            count = session.execute(
                text(
                    "SELECT count() FROM system.columns WHERE database = :database "
                    "AND table = 'siri_vehicle_location'"
                ),
                {"database": os.getenv("CLICKHOUSE_DATABASE", "default")},
            ).scalar()
            self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
