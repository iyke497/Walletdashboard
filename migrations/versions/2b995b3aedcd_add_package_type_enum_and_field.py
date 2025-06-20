"""Add package type enum and field

Revision ID: 2b995b3aedcd
Revises: 417c84e0f751
Create Date: 2025-06-15 13:30:19.433167

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b995b3aedcd'
down_revision = '417c84e0f751'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # Create the enum type first
    package_type_enum = sa.Enum('BASIC', 'PRO', 'ENTERPRISE', 'CUSTOM', name='packagetype')
    package_type_enum.create(op.get_bind())
    
    # Add column as nullable first
    with op.batch_alter_table('hashrate_packages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('package_type', package_type_enum, nullable=True))

    # Set default value for existing rows
    op.execute("UPDATE hashrate_packages SET package_type = 'BASIC'")

    # Now alter the column to be NOT NULL
    with op.batch_alter_table('hashrate_packages', schema=None) as batch_op:
        batch_op.alter_column('package_type', nullable=False)

    # ### end Alembic commands ###

def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('hashrate_packages', schema=None) as batch_op:
        batch_op.drop_column('package_type')
    
    # Drop the enum type
    sa.Enum(name='packagetype').drop(op.get_bind())
    # ### end Alembic commands ###