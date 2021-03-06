"""add fields for etl

Revision ID: 4767d09f46df
Revises: a39d8d6dcc87
Create Date: 2021-05-06 06:55:52.741680+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4767d09f46df'
down_revision = 'a39d8d6dcc87'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ride', sa.Column('journey_ref', sa.String(), nullable=True))
    op.add_column('ride', sa.Column('scheduled_start_time', sa.DateTime(), nullable=True))
    op.add_column('ride', sa.Column('vehicle_ref', sa.String(), nullable=True))
    op.add_column('ride', sa.Column('is_from_gtfs', sa.Boolean(), nullable=True))
    op.add_column('route_stop', sa.Column('order', sa.Integer(), nullable=True))
    op.add_column('route_stop', sa.Column('is_from_gtfs', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('route_stop', 'is_from_gtfs')
    op.drop_column('route_stop', 'order')
    op.drop_column('ride', 'is_from_gtfs')
    op.drop_column('ride', 'vehicle_ref')
    op.drop_column('ride', 'scheduled_start_time')
    op.drop_column('ride', 'journey_ref')
    # ### end Alembic commands ###
