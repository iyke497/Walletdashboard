"""Add email verification fields

Revision ID: 39c175a11c4e
Revises: 5193db8d2f8e
Create Date: 2025-06-04 00:14:45.651263

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = '39c175a11c4e'
down_revision = '5193db8d2f8e'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns as nullable first
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('email_verification_token', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True))
        batch_op.drop_constraint('uq_users_email', type_='unique')
        batch_op.create_unique_constraint('uq_users_email_verification_token', ['email_verification_token'])
        batch_op.drop_column('verified')
        batch_op.drop_column('token_expiration')
        batch_op.drop_column('verification_token')

    # Update existing rows to set email_verified = 0
    op.execute(text("UPDATE users SET email_verified = 0"))

    # Now alter the column to be NOT NULL
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('email_verified', nullable=False)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('verification_token', sa.VARCHAR(length=255), nullable=True))
        batch_op.add_column(sa.Column('token_expiration', sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('verified', sa.BOOLEAN(), server_default=sa.text("'0'"), nullable=False))
        batch_op.drop_constraint('uq_users_email_verification_token', type_='unique')
        batch_op.create_unique_constraint('uq_users_email', ['email'])
        batch_op.drop_column('email_verification_sent_at')
        batch_op.drop_column('email_verification_token')
        batch_op.drop_column('email_verified')
        