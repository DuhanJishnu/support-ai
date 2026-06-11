"""Core support platform ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    """Rider account used by support workflows."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone_number: Mapped[str] = mapped_column(String(32))
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), default=Decimal("5.0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    rides: Mapped[list[Ride]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    support_tickets: Mapped[list[SupportTicket]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Ride(Base):
    """Ride facts used by billing and telemetry agents."""

    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    driver_name: Mapped[str] = mapped_column(String(120))
    pickup_address: Mapped[str] = mapped_column(String(255))
    dropoff_address: Mapped[str] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    distance_km: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    fare_amount: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    gps_deviation_meters: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="rides")
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="ride",
        cascade="all, delete-orphan",
    )
    support_tickets: Mapped[list[SupportTicket]] = relationship(back_populates="ride")


class Transaction(Base):
    """Payment record associated with a ride."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    ride_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(32), default="succeeded")
    payment_method: Mapped[str] = mapped_column(String(40))
    processor_reference: Mapped[str] = mapped_column(String(80), unique=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    ride: Mapped[Ride] = relationship(back_populates="transactions")
    user: Mapped[User] = relationship(back_populates="transactions")


class SupportTicket(Base):
    """Customer support issue tied to a rider and optionally a ride."""

    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="SET NULL"),
    )
    category: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32), index=True, default="open")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    subject: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="support_tickets")
    ride: Mapped[Ride | None] = relationship(back_populates="support_tickets")
