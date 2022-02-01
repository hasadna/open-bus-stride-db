"""add siri_ride.gtfs_ride_id

Revision ID: 10d0aa14d96b
Revises: baadbcbcd3de
Create Date: 2022-02-01 08:49:41.434350+00:00

"""
from alembic import op
import sqlalchemy as sa


import open_bus_stride_db


# revision identifiers, used by Alembic.
revision = '10d0aa14d96b'
down_revision = 'baadbcbcd3de'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('siri_ride', sa.Column('gtfs_ride_id', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('siri_ride', 'gtfs_ride_id')
    # ### end Alembic commands ###
