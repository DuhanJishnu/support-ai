"""Seed realistic support data for local development."""

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ride, SupportTicket, Transaction, User
from app.db.session import async_session_factory

NAMES = [
    "Avery Chen",
    "Jordan Smith",
    "Maya Patel",
    "Noah Williams",
    "Sophia Garcia",
    "Liam Johnson",
    "Emma Rodriguez",
    "Ethan Brown",
    "Olivia Davis",
    "Lucas Martinez",
]
DRIVERS = [
    "Priya Nair",
    "Marcus Lee",
    "Samir Khan",
    "Nina Brooks",
    "Diego Santos",
    "Grace Miller",
]
LOCATIONS = [
    "Union Station",
    "Central Market",
    "Riverside Hotel",
    "Tech Park Gate 3",
    "City Hospital",
    "Museum Plaza",
    "Airport Terminal 2",
    "Maple Street Apartments",
    "Downtown Arena",
    "North Campus",
]
PAYMENT_METHODS = ["visa_4242", "mastercard_4444", "amex_0005", "wallet_balance"]


def money(value: float) -> Decimal:
    """Return a Decimal rounded to cents."""
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def clear_existing_data(session: AsyncSession) -> None:
    """Clear tables in dependency order so the seed is repeatable."""
    for model in (SupportTicket, Transaction, Ride, User):
        await session.execute(delete(model))


def build_ticket(
    *,
    user_id: uuid.UUID,
    ride_id: uuid.UUID,
    issue_type: str,
    created_at: datetime,
) -> SupportTicket:
    """Create a ticket that matches a known anomaly."""
    subjects = {
        "double_charge": "I was charged twice for the same ride",
        "gps_discrepancy": "My route looks much longer than expected",
        "general": "Question about my completed trip",
    }
    descriptions = {
        "double_charge": (
            "The app shows two successful payments for one completed ride."
        ),
        "gps_discrepancy": (
            "The driver took a route that does not match the map estimate."
        ),
        "general": "Please review this ride and confirm the final fare.",
    }
    return SupportTicket(
        id=uuid.uuid4(),
        user_id=user_id,
        ride_id=ride_id,
        category="billing" if issue_type == "double_charge" else "ride_quality",
        status="open",
        priority=4 if issue_type != "general" else 2,
        subject=subjects[issue_type],
        description=descriptions[issue_type],
        created_at=created_at + timedelta(hours=1),
        resolved_at=None,
    )


async def seed() -> None:
    """Populate users, rides, transactions, and support tickets."""
    random.seed(42)
    async with async_session_factory() as session:
        await clear_existing_data(session)

        now = datetime.now(tz=UTC)
        users = [
            User(
                id=uuid.uuid4(),
                full_name=name,
                email=f"{name.lower().replace(' ', '.')}@example.com",
                phone_number=f"+1555{index:07d}",
                rating=Decimal(f"{random.uniform(4.3, 5.0):.1f}"),
                created_at=now - timedelta(days=random.randint(60, 365)),
            )
            for index, name in enumerate(NAMES, start=1000)
        ]
        session.add_all(users)

        rides: list[Ride] = []
        transactions: list[Transaction] = []
        tickets: list[SupportTicket] = []

        for index in range(50):
            user = users[index % len(users)]
            requested_at = now - timedelta(days=random.randint(1, 45), hours=index)
            distance = round(random.uniform(2.2, 32.0), 2)
            fare = money(4.75 + distance * random.uniform(1.15, 2.35))
            issue_type = "general"
            gps_deviation = random.randint(15, 240)

            if index in {7, 18, 34, 45}:
                issue_type = "double_charge"
            elif index in {5, 14, 29, 41}:
                issue_type = "gps_discrepancy"
                gps_deviation = random.randint(900, 2400)

            ride = Ride(
                id=uuid.uuid4(),
                user_id=user.id,
                driver_name=random.choice(DRIVERS),
                pickup_address=random.choice(LOCATIONS),
                dropoff_address=random.choice(LOCATIONS),
                requested_at=requested_at,
                completed_at=requested_at + timedelta(minutes=random.randint(8, 55)),
                status="completed",
                distance_km=money(distance),
                fare_amount=fare,
                gps_deviation_meters=gps_deviation,
                notes=(
                    "GPS anomaly detected by telemetry"
                    if issue_type == "gps_discrepancy"
                    else None
                ),
            )
            rides.append(ride)

            transaction = Transaction(
                id=uuid.uuid4(),
                ride_id=ride.id,
                user_id=user.id,
                amount=fare,
                currency="USD",
                status="succeeded",
                payment_method=random.choice(PAYMENT_METHODS),
                processor_reference=f"txn_{index:04d}_{uuid.uuid4().hex[:10]}",
                is_duplicate=False,
                created_at=ride.completed_at or requested_at,
            )
            transactions.append(transaction)

            if issue_type == "double_charge":
                transactions.append(
                    Transaction(
                        id=uuid.uuid4(),
                        ride_id=ride.id,
                        user_id=user.id,
                        amount=fare,
                        currency="USD",
                        status="succeeded",
                        payment_method=transaction.payment_method,
                        processor_reference=f"txn_dup_{index:04d}_{uuid.uuid4().hex[:8]}",
                        is_duplicate=True,
                        created_at=transaction.created_at + timedelta(minutes=2),
                    )
                )

            if issue_type != "general" or index % 9 == 0:
                tickets.append(
                    build_ticket(
                        user_id=user.id,
                        ride_id=ride.id,
                        issue_type=issue_type,
                        created_at=requested_at,
                    )
                )

        session.add_all(rides)
        session.add_all(transactions)
        session.add_all(tickets)
        await session.commit()

    print(
        "Seeded 10 users, 50 rides, "
        f"{len(transactions)} transactions, and {len(tickets)} support tickets."
    )


if __name__ == "__main__":
    asyncio.run(seed())
