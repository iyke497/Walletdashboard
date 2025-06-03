"""Add email verification fields

Revision ID: 1a02ca58c0dc
Revises: 5193db8d2f8e
Create Date: 2025-06-03 23:15:11.346805

"""
# migrations/versions/1a02ca58c0dc_add_email_verification_fields.py
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1a02ca58c0dc'
down_revision = '5193db8d2f8e' # Make sure this is correct
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Add the new columns
        batch_op.add_column(sa.Column('verified', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('verification_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('token_expiration', sa.DateTime(), nullable=True))

        # IMPORTANT: If you added any unique or foreign key constraints, they need a name.
        # Example for a UNIQUE constraint on 'email' if it wasn't already unique:
        # Make sure 'email' column already exists in 'users' table
        # If 'email' is already unique via a model definition, you might not need this here.
        # But if Alembic is complaining, it means it's trying to create one implicitly without a name.
        try:
            batch_op.create_unique_constraint('uq_users_email', ['email']) # Provide a unique name
        except Exception as e:
            # Handle cases where the constraint might already exist or other issues
            print(f"Warning: Could not create unique constraint 'uq_users_email' on 'users.email': {e}")
            pass # Or handle appropriately

        # Example for a FOREIGN KEY constraint (if you were adding one related to users)
        # batch_op.create_foreign_key('fk_some_table_user_id', 'some_table', ['user_id'], ['id']) # Example

def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Remove the columns in reverse order of addition
        batch_op.drop_column('token_expiration')
        batch_op.drop_column('verification_token')
        batch_op.drop_column('verified')

        # If you added a unique constraint in upgrade, drop it here as well
        try:
            batch_op.drop_constraint('uq_users_email', type_='unique')
        except Exception as e:
            print(f"Warning: Could not drop unique constraint 'uq_users_email' on 'users.email': {e}")
            pass