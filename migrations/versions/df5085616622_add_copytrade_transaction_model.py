"""Add copytrade transaction model

Revision ID: df5085616622
Revises: 6f186382f59e
Create Date: 2025-06-21 14:34:14.960197

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df5085616622'
down_revision = '6f186382f59e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('copy_trade_transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('follower_id', sa.Integer(), nullable=False),
    sa.Column('copy_trade_id', sa.Integer(), nullable=False),
    sa.Column('base_asset_id', sa.Integer(), nullable=False),
    sa.Column('quote_asset_id', sa.Integer(), nullable=False),
    sa.Column('trade_type', sa.String(length=10), nullable=False),
    sa.Column('amount', sa.Numeric(precision=30, scale=18), nullable=False),
    sa.Column('price', sa.Numeric(precision=30, scale=18), nullable=False),
    sa.Column('pnl', sa.Numeric(precision=15, scale=2), nullable=False),
    sa.Column('pnl_percentage', sa.Numeric(precision=8, scale=4), nullable=False),
    sa.Column('external_tx_id', sa.String(length=100), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('remark', sa.Text(), nullable=True),
    sa.Column('transaction_timestamp', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint('amount > 0', name='ck_copy_tx_amount_positive'),
    sa.CheckConstraint('price > 0', name='ck_copy_tx_price_positive'),
    sa.ForeignKeyConstraint(['base_asset_id'], ['assets.id'], ),
    sa.ForeignKeyConstraint(['copy_trade_id'], ['copy_trades.id'], ),
    sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['quote_asset_id'], ['assets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('copy_trade_transactions', schema=None) as batch_op:
        batch_op.create_index('idx_copy_tx_follower_status', ['follower_id', 'status'], unique=False)
        batch_op.create_index('idx_copy_tx_timestamp', ['transaction_timestamp'], unique=False)
        batch_op.create_index(batch_op.f('ix_copy_trade_transactions_copy_trade_id'), ['copy_trade_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_copy_trade_transactions_follower_id'), ['follower_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_copy_trade_transactions_transaction_timestamp'), ['transaction_timestamp'], unique=False)

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('tx_type',
               existing_type=sa.VARCHAR(length=10),
               type_=sa.Enum('DEPOSIT', 'WITHDRAW', 'TRADE_BUY', 'TRADE_SELL', 'STAKE', 'UNSTAKE', 'FEE', 'TRANSFER_IN', 'TRANSFER_OUT', name='transactiontype'),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('tx_type',
               existing_type=sa.Enum('DEPOSIT', 'WITHDRAW', 'TRADE_BUY', 'TRADE_SELL', 'STAKE', 'UNSTAKE', 'FEE', 'TRANSFER_IN', 'TRANSFER_OUT', name='transactiontype'),
               type_=sa.VARCHAR(length=10),
               existing_nullable=False)

    with op.batch_alter_table('copy_trade_transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_copy_trade_transactions_transaction_timestamp'))
        batch_op.drop_index(batch_op.f('ix_copy_trade_transactions_follower_id'))
        batch_op.drop_index(batch_op.f('ix_copy_trade_transactions_copy_trade_id'))
        batch_op.drop_index('idx_copy_tx_timestamp')
        batch_op.drop_index('idx_copy_tx_follower_status')

    op.drop_table('copy_trade_transactions')
    # ### end Alembic commands ###
