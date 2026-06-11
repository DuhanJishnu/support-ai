import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.db.base import Base
from app.db.models import Ride, SupportTicket, Transaction, User


def test_support_models_are_registered_with_metadata():
    """Day 4 models should be available to Alembic through Base metadata."""
    assert {"users", "rides", "transactions", "support_tickets"}.issubset(
        Base.metadata.tables
    )


def test_model_relationships_can_be_composed_in_memory():
    """Verify the ORM relationship graph without requiring a live database."""
    user = User(
        id=uuid.uuid4(),
        full_name="Maya Patel",
        email="maya.patel@example.com",
        phone_number="+15551001000",
        rating=Decimal("4.9"),
    )
    ride = Ride(
        id=uuid.uuid4(),
        user=user,
        driver_name="Priya Nair",
        pickup_address="Union Station",
        dropoff_address="Airport Terminal 2",
        requested_at=datetime.now(tz=UTC),
        completed_at=datetime.now(tz=UTC),
        status="completed",
        distance_km=Decimal("12.40"),
        fare_amount=Decimal("24.75"),
        gps_deviation_meters=1450,
        notes="GPS anomaly detected by telemetry",
    )
    transaction = Transaction(
        id=uuid.uuid4(),
        ride=ride,
        user=user,
        amount=Decimal("24.75"),
        currency="USD",
        status="succeeded",
        payment_method="visa_4242",
        processor_reference="txn_test_001",
        is_duplicate=True,
        created_at=datetime.now(tz=UTC),
    )
    ticket = SupportTicket(
        id=uuid.uuid4(),
        user=user,
        ride=ride,
        category="billing",
        status="open",
        priority=4,
        subject="I was charged twice for the same ride",
        description="The app shows duplicate successful payments.",
        created_at=datetime.now(tz=UTC),
        resolved_at=None,
    )

    assert ride in user.rides
    assert transaction in ride.transactions
    assert ticket in user.support_tickets
    assert ticket.ride is ride
