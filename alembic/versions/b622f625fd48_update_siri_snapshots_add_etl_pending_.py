"""update siri_snapshots: add etl_pending status and time

Revision ID: b622f625fd48
Revises: a2518a3f5578
Create Date: 2022-08-08 17:14:45.198727+00:00

"""
from alembic import op
import sqlalchemy as sa


import open_bus_stride_db


# revision identifiers, used by Alembic.
revision = 'b622f625fd48'
down_revision = 'a2518a3f5578'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('siri_snapshot', sa.Column('etl_pending_time', open_bus_stride_db.model.base.DateTimeWithTimeZone(), nullable=True))
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE etlstatusenum ADD VALUE 'pending'")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('siri_snapshot', 'etl_pending_time')
    # ### end Alembic commands ###