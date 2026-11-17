import os
import threading
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.events.models import Distance, Event, EventStatus
from app.modules.registrations.models import Registration
from app.modules.registrations.waiver import WAIVER_VERSION

URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not URL.startswith("postgresql"), reason="needs a real PostgreSQL: set TEST_DATABASE_URL"
)

PROFILE = {
    "date_of_birth": "1990-05-14", "gender": "female", "phone": "0712345678", "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau", "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}


@pytest.fixture
def pg():
    """Real PostgreSQL with a separate connection per request, exactly as in production."""
    engine = create_engine(URL, pool_size=10)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def per_request_session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = per_request_session
    yield Session
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_event(Session, capacity):
    today = date.today()
    with Session() as s:
        event = Event(
            name="Last Spot Run", event_date=today + timedelta(days=30), location="Nakuru",
            registration_opens=today - timedelta(days=1), registration_closes=today + timedelta(days=20),
            status=EventStatus.published,
            distances=[Distance(name="5K", km=Decimal("5"), fee=Decimal("500"), capacity=capacity, min_age=12)],
        )
        s.add(event)
        s.commit()
        return event.id, event.distances[0].id


def new_runner(i):
    c = TestClient(app)
    res = c.post("/api/v1/auth/signup", json={
        "full_name": f"Runner {i}", "email": f"runner{i}@example.com", "password": "correct-horse-1",
    })
    assert res.status_code == 201, res.text
    assert c.put("/api/v1/runners/me", json=PROFILE).status_code == 200
    return c


def race(clients, event_id, distance_id):
    """Every runner presses Register at the same instant, each on a thread of their own."""
    barrier = threading.Barrier(len(clients))
    results = [None] * len(clients)

    def go(i, c):
        barrier.wait()
        res = c.post(
            f"/api/v1/events/{event_id}/registrations",
            json={"distance_id": str(distance_id), "waiver_version": WAIVER_VERSION},
        )
        results[i] = (res.status_code, res.json())

    threads = [threading.Thread(target=go, args=(i, c)) for i, c in enumerate(clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert all(r is not None for r in results), "a request never finished (a deadlock?)"
    return results


def test_only_one_runner_gets_the_last_spot(pg):
    event_id, distance_id = make_event(pg, capacity=1)
    results = race([new_runner(i) for i in range(6)], event_id, distance_id)
    assert sorted(code for code, _ in results) == [201, 409, 409, 409, 409, 409], results
    assert {body["detail"]["code"] for code, body in results if code == 409} == {"sold_out"}
    with pg() as s:
        assert s.scalar(select(func.count(Registration.id)).where(Registration.distance_id == distance_id)) == 1


def test_bib_numbers_stay_unique_when_runners_register_at_once(pg):
    event_id, distance_id = make_event(pg, capacity=10)
    results = race([new_runner(i) for i in range(6)], event_id, distance_id)
    assert [code for code, _ in results] == [201] * 6, results
    assert sorted(body["bib_number"] for _, body in results) == [1, 2, 3, 4, 5, 6]