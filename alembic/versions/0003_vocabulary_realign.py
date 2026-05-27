"""migrate status/action values to canonical vocabulary

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ParkingSession status: active->running, completed->pending_settlement,
    #                        paid->settled, expired->cancelled
    op.execute("UPDATE parking_sessions SET status = 'running' WHERE status = 'active'")
    op.execute("UPDATE parking_sessions SET status = 'pending_settlement' WHERE status = 'completed'")
    op.execute("UPDATE parking_sessions SET status = 'settled' WHERE status = 'paid'")
    op.execute("UPDATE parking_sessions SET status = 'cancelled' WHERE status = 'expired'")
    op.execute("UPDATE parking_sessions SET status = 'running' WHERE status IS NULL OR status NOT IN ('running','pending_settlement','settled','cancelled')")

    # Transaction action: payment->session_fee, park->session_fee
    op.execute("UPDATE transactions SET action = 'session_fee' WHERE action = 'payment'")
    op.execute("UPDATE transactions SET action = 'session_fee' WHERE action = 'park'")

    # LedgerOutbox status: processed->delivered
    op.execute("UPDATE ledger_outbox SET status = 'delivered' WHERE status = 'processed'")

    # Update server_default — SQLite-friendly: use batch mode workaround
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("parking_sessions", "status", server_default="running")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("parking_sessions", "status", server_default="active")

    op.execute("UPDATE ledger_outbox SET status = 'processed' WHERE status = 'delivered'")

    op.execute("UPDATE transactions SET action = 'payment' WHERE action = 'session_fee'")

    op.execute("UPDATE parking_sessions SET status = 'expired' WHERE status = 'cancelled'")
    op.execute("UPDATE parking_sessions SET status = 'paid' WHERE status = 'settled'")
    op.execute("UPDATE parking_sessions SET status = 'completed' WHERE status = 'pending_settlement'")
    op.execute("UPDATE parking_sessions SET status = 'active' WHERE status = 'running'")
