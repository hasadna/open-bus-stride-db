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
    op.create_table('siri_agg_velocity_stats',
        sa.Column('lon_round', sa.Float(), nullable=False),
        sa.Column('lat_round', sa.Float(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('stddev_hourly_avg', sa.Float(), nullable=True),
        sa.Column('avg_hourly_avg', sa.Float(), nullable=True),
        sa.Column('sample_number', sa.Integer(), nullable=True),
        sa.Column('median_hourly_avg', sa.Float(), nullable=True),
        sa.Column('last_used', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('lon_round', 'lat_round', 'date')
    )
    op.create_index(op.f('ix_siri_agg_velocity_stats_date'), 'siri_agg_velocity_stats', ['date'], unique=False)
    op.create_index(op.f('ix_siri_agg_velocity_stats_lon_round_lat_round'), 'siri_agg_velocity_stats', ['lon_round', 'lat_round'], unique=False)
    op.create_index(op.f('ix_siri_agg_velocity_stats_last_used'), 'siri_agg_velocity_stats', ['last_used'], unique=False)

def downgrade():
    op.drop_table('siri_agg_velocity_stats')
    pass
