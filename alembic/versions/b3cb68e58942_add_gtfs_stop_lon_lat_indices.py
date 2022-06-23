"""add gtfs_stop lon/lat indices

Revision ID: b3cb68e58942
Revises: c0fa93cfbf95
Create Date: 2022-06-23 08:00:00.432163+00:00

"""
from alembic import op
import sqlalchemy as sa


import open_bus_stride_db


# revision identifiers, used by Alembic.
revision = 'b3cb68e58942'
down_revision = 'c0fa93cfbf95'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_gtfs_stop_lat'), 'gtfs_stop', ['lat'], unique=False)
    op.create_index(op.f('ix_gtfs_stop_lon'), 'gtfs_stop', ['lon'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_gtfs_stop_lon'), table_name='gtfs_stop')
    op.drop_index(op.f('ix_gtfs_stop_lat'), table_name='gtfs_stop')
    # ### end Alembic commands ###
