"""add resident_profiles, share_listings, share_bookings tables

Revision ID: 0016
Revises: 9dfac872075f
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "9dfac872075f"
branch_labels = None


def upgrade():
    op.create_table(
        "resident_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "slot_id",
            sa.Integer(),
            sa.ForeignKey("micro_slots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permit_type",
            sa.String(20),
            server_default="monthly",
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("monthly_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("auto_renew", sa.Boolean(), server_default="1"),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", name="uq_resident_slot"),
    )
    op.create_index(
        "ix_resident_profiles_user_id", "resident_profiles", ["user_id"]
    )
    op.create_index(
        "ix_resident_profiles_slot_id", "resident_profiles", ["slot_id"]
    )

    op.create_table(
        "share_listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "resident_profile_id",
            sa.Integer(),
            sa.ForeignKey("resident_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "slot_id",
            sa.Integer(),
            sa.ForeignKey("micro_slots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_per_hour", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "available_from", sa.String(5), server_default="00:00"
        ),
        sa.Column(
            "available_until", sa.String(5), server_default="23:59"
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "max_advance_days", sa.Integer(), server_default="7"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_share_listings_resident_profile_id",
        "share_listings",
        ["resident_profile_id"],
    )
    op.create_index(
        "ix_share_listings_slot_id", "share_listings", ["slot_id"]
    )
    op.create_index(
        "ix_share_listings_status", "share_listings", ["status"]
    )

    op.create_table(
        "share_bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "share_listing_id",
            sa.Integer(),
            sa.ForeignKey("share_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("driver_id", sa.String(100), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("total_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("platform_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("owner_payout", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default="active",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_share_bookings_share_listing_id",
        "share_bookings",
        ["share_listing_id"],
    )
    op.create_index(
        "ix_share_bookings_driver_id", "share_bookings", ["driver_id"]
    )
    op.create_index(
        "ix_share_bookings_status", "share_bookings", ["status"]
    )


def downgrade():
    op.drop_table("share_bookings")
    op.drop_table("share_listings")
    op.drop_table("resident_profiles")
