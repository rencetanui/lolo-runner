from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.events.models import Distance, Event
from app.modules.auth import models as _auth_models

@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_event(db):
    def _make(name="Test Run", days_from_now=30):
        today = date.today()
        event = Event(
            name=name,
            event_date=today + timedelta(days=days_from_now),
            location="Nakuru",
            registration_opens=today - timedelta(days=10),
            registration_closes=today + timedelta(days=days_from_now - 5),
            distances=[
                Distance(name="5K", km=Decimal("5"), fee=Decimal("500"), capacity=100),
                Distance(name="10K", km=Decimal("10"), fee=Decimal("800"), capacity=100),
            ],
        )
        db.add(event)
        db.commit()
        return event
    return _make