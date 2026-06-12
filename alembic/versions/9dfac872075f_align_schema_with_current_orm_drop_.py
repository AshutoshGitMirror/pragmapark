"""align schema with current ORM (drop removed tables, update slot_current_state)

Revision ID: 9dfac872075f
Revises: 0015
Create Date: 2026-06-12 10:49:30.679277
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '9dfac872075f'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop tables that were removed from src.api.database ORM models
    # (blockchain_blocks, blockchain_pending_tx, ipfs_store,
    #  parking_pool_records, zone_snapshots, dt_config, twin_state_history)
    op.drop_table('dt_config')
    op.drop_table('zone_snapshots')
    op.drop_table('ipfs_store')
    op.drop_table('parking_pool_records')
    op.drop_table('blockchain_blocks')
    op.drop_table('blockchain_pending_tx')
    op.drop_index(op.f('ix_twin_state_history_timestamp'), table_name='twin_state_history')
    op.drop_index(op.f('ix_twin_state_history_zone_id'), table_name='twin_state_history')
    op.drop_table('twin_state_history')

    # Remove index on rate_limit_windows.window_start (no longer in ORM)
    op.drop_index(op.f('ix_rate_limit_windows_window_start'), table_name='rate_limit_windows')

    # Remodel slot_current_state to match ORM:
    #   - Add id as new primary key (was slot_id)
    #   - Drop 5 unused columns (driver_id, expires_at, prebook_*)
    #   - Change updated_at from FLOAT NOT NULL to Integer nullable
    #   - Add unique index on slot_id
    with op.batch_alter_table('slot_current_state') as batch_op:
        batch_op.add_column(sa.Column('id', sa.Integer(), nullable=False))
        batch_op.alter_column('updated_at',
               existing_type=sa.FLOAT(),
               type_=sa.Integer(),
               existing_nullable=False,
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.create_index(op.f('ix_slot_current_state_slot_id'), ['slot_id'], unique=True)
        batch_op.drop_column('prebook_driver_id')
        batch_op.drop_column('prebook_target')
        batch_op.drop_column('prebook_expires_at')
        batch_op.drop_column('expires_at')
        batch_op.drop_column('driver_id')


def downgrade() -> None:
    # Reverse slot_current_state changes
    with op.batch_alter_table('slot_current_state') as batch_op:
        batch_op.add_column(sa.Column('driver_id', sa.VARCHAR(length=100), nullable=True))
        batch_op.add_column(sa.Column('expires_at', sa.FLOAT(), nullable=True))
        batch_op.add_column(sa.Column('prebook_expires_at', sa.FLOAT(), nullable=True))
        batch_op.add_column(sa.Column('prebook_target', sa.FLOAT(), nullable=True))
        batch_op.add_column(sa.Column('prebook_driver_id', sa.VARCHAR(length=100), nullable=True))
        batch_op.drop_index(op.f('ix_slot_current_state_slot_id'), table_name='slot_current_state')
        batch_op.alter_column('updated_at',
               existing_type=sa.Integer(),
               type_=sa.FLOAT(),
               existing_nullable=True,
               nullable=False,
               existing_server_default=sa.text("'0'"))
        batch_op.drop_column('id')

    # Restore removed indexes and tables
    op.create_index(op.f('ix_rate_limit_windows_window_start'), 'rate_limit_windows', ['window_start'], unique=False)

    op.create_table('twin_state_history',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('timestamp', sa.FLOAT(), nullable=False),
    sa.Column('zone_id', sa.VARCHAR(length=50), nullable=False),
    sa.Column('occupancy_rate', sa.FLOAT(), nullable=False),
    sa.Column('price', sa.FLOAT(), nullable=False),
    sa.Column('total_slots', sa.INTEGER(), nullable=False),
    sa.Column('flux', sa.FLOAT(), server_default=sa.text("'0'"), nullable=True),
    sa.Column('congestion_level', sa.VARCHAR(length=20), server_default=sa.text("'normal'"), nullable=True),
    sa.Column('stid_prediction', sa.FLOAT(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_twin_state_history_zone_id'), 'twin_state_history', ['zone_id'], unique=False)
    op.create_index(op.f('ix_twin_state_history_timestamp'), 'twin_state_history', ['timestamp'], unique=False)

    op.create_table('blockchain_pending_tx',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('tx_data', sa.TEXT(), nullable=False),
    sa.Column('created_at', sa.FLOAT(), server_default=sa.text("'0'"), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('blockchain_blocks',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('index', sa.INTEGER(), nullable=False),
    sa.Column('timestamp', sa.FLOAT(), nullable=False),
    sa.Column('transactions', sa.TEXT(), nullable=False),
    sa.Column('previous_hash', sa.VARCHAR(length=64), nullable=False),
    sa.Column('nonce', sa.INTEGER(), server_default=sa.text("'0'"), nullable=True),
    sa.Column('hash', sa.VARCHAR(length=64), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hash'),
    sa.UniqueConstraint('index')
    )
    op.create_table('parking_pool_records',
    sa.Column('pool_id', sa.VARCHAR(length=50), nullable=False),
    sa.Column('total_spots', sa.INTEGER(), nullable=False),
    sa.Column('owner', sa.VARCHAR(length=100), nullable=False),
    sa.Column('data', sa.TEXT(), nullable=False),
    sa.Column('updated_at', sa.FLOAT(), server_default=sa.text("'0'"), nullable=False),
    sa.PrimaryKeyConstraint('pool_id')
    )
    op.create_table('ipfs_store',
    sa.Column('cid', sa.VARCHAR(length=64), nullable=False),
    sa.Column('data', sa.TEXT(), nullable=False),
    sa.Column('content_type', sa.VARCHAR(length=50), server_default=sa.text("'generic'"), nullable=True),
    sa.Column('timestamp', sa.FLOAT(), nullable=False),
    sa.Column('size_bytes', sa.INTEGER(), server_default=sa.text("'0'"), nullable=True),
    sa.Column('pinned', sa.INTEGER(), server_default=sa.text("'1'"), nullable=True),
    sa.PrimaryKeyConstraint('cid')
    )
    op.create_table('zone_snapshots',
    sa.Column('zone_id', sa.VARCHAR(length=50), nullable=False),
    sa.Column('capacity', sa.INTEGER(), nullable=False),
    sa.Column('occupancy_rate', sa.FLOAT(), server_default=sa.text("'0.3'"), nullable=False),
    sa.Column('price', sa.FLOAT(), server_default=sa.text("'10.0'"), nullable=False),
    sa.Column('updated_at', sa.FLOAT(), server_default=sa.text("'0'"), nullable=False),
    sa.PrimaryKeyConstraint('zone_id')
    )
    op.create_table('dt_config',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('current_time', sa.FLOAT(), server_default=sa.text("'0'"), nullable=False),
    sa.Column('stid_weights', sa.TEXT(), nullable=True),
    sa.Column('updated_at', sa.FLOAT(), server_default=sa.text("'0'"), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
