from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.modules.events.models import Distance, Event


def d(name, km, fee, capacity, min_age=12):
    return Distance(name=name, km=Decimal(km), fee=Decimal(fee), capacity=capacity, min_age=min_age)


def build_events() -> list[Event]:
    today = date.today()
    return [
        Event(
            name="Nakuru Sunrise Run",
            event_date=today + timedelta(days=45),
            location="Nakuru",
            registration_opens=today - timedelta(days=5),
            registration_closes=today + timedelta(days=38),
            distances=[d("5K", "5", "500", 500), d("10K", "10", "800", 400)],
        ),
        Event(
            name="Rift Valley Half Marathon",
            event_date=today + timedelta(days=90),
            location="Naivasha",
            registration_opens=today + timedelta(days=10),
            registration_closes=today + timedelta(days=80),
            distances=[
                d("10K", "10", "1000", 600, 14),
                d("21K", "21.1", "1800", 800, 16),
                d("42K", "42.2", "2500", 300, 18),
            ],
        ),
        Event(
            name="Hill Trail Challenge",
            event_date=today - timedelta(days=30),   # past event, useful for testing filters
            location="Kericho",
            registration_opens=today - timedelta(days=100),
            registration_closes=today - timedelta(days=35),
            distances=[d("15K", "15", "1200", 250, 16)],
        ),
    ]


def main():
    with SessionLocal() as db:
        existing = set(db.scalars(select(Event.name)))
        new = [e for e in build_events() if e.name not in existing]
        db.add_all(new)
        db.commit()
        print(f"Seeded {len(new)} event(s); {len(existing)} already present.")


if __name__ == "__main__":
    main()