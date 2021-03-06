"""add Stop

Revision ID: 78d860ffa426
Revises: 20f920736aab
Create Date: 2021-05-05 06:37:18.120482+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '78d860ffa426'
down_revision = '20f920736aab'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('stop',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('min_date', sa.Date(), nullable=True),
    sa.Column('max_date', sa.Date(), nullable=True),
    sa.Column('code', sa.Integer(), nullable=True),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lon', sa.Float(), nullable=True),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('city', sa.String(), nullable=True),
    sa.Column('is_from_gtfs', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('stop')
    # ### end Alembic commands ###
