"""Add materialized view siri_agg_velocity_stats

Revision ID: 589113bd8e5e
Revises: eb501cf9f471
Create Date: 2024-12-16 18:05:19.088109+00:00

"""
from alembic import op
import sqlalchemy as sa


import open_bus_stride_db


# revision identifiers, used by Alembic.
revision = '589113bd8e5e'
down_revision = 'eb501cf9f471'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS siri_agg_velocity_stats")
    op.execute("""
        create materialized view siri_agg_velocity_stats as
        WITH HourlyAverages AS (
            SELECT
                trunc(lon * 500 + .5)/500 AS lonRound,
                trunc(lat * 500 + .5)/500 AS latRound,
                DATE(recorded_at_time) AS date,
                DATE_PART('hour', recorded_at_time) AS hour,
                AVG(velocity) AS hourly_avg,
                COUNT(1) as sample_number
            FROM siri_vehicle_location svl
            WHERE velocity > 0 AND velocity < 200 AND lon > 0 and lat > 0
            GROUP BY lonRound, latRound, date, hour
            having COUNT(1) > 5
        )
        SELECT
            lonRound,
            latRound,
            date,
            STDDEV(hourly_avg) AS stddev_hourly_avg,
            AVG(hourly_avg) AS avg_hourly_avg,
            SUM(sample_number) as sample_number,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY hourly_avg) AS median_hourly_avg
        FROM HourlyAverages
        GROUP BY lonRound, latRound, date;
    """)
    op.execute("create index idx_siri_agg_velocity_stats_lonRound_latRound on siri_agg_velocity_stats (lonRound, latRound)")
    op.execute("create index idx_siri_agg_velocity_stats_date on siri_agg_velocity_stats (date)")
    op.execute("REFRESH MATERIALIZED VIEW siri_agg_velocity_stats")
    # This unique index allows to refresh the materialized view concurrently (it was created manually)
    op.execute("create unique index siri_agg_velocity_stats_uniq_idx on siri_agg_velocity_stats (lonRound, latRound, date);")

def downgrade():
    op.execute("drop materialized view if exists siri_agg_velocity_stats")
