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
from app.modules.runners import models as _runner_models
from app.modules.registrations import models as _registration_models
from app.modules.payments import models as _payment_models
from app.modules.payments.providers.mpesa import MpesaError, MpesaProcessing, get_mpesa_client
from app.modules.notifications import models as _notification_models  # noqa: F401
from app.core.config import settings
from app.modules.audit import models as _audit_models
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

class FakeMpesa:
    def __init__(self):
        self.pushes = []
        self.fail_push = False
        self.query_result = None          # None means "customer hasn't answered yet"

    def stk_push(self, *, phone, amount, reference, description):
        if self.fail_push:
            raise MpesaError("simulated outage")
        n = len(self.pushes) + 1
        self.pushes.append({"phone": phone, "amount": amount, "reference": reference})
        return {"MerchantRequestID": f"m_{n}", "CheckoutRequestID": f"ws_CO_{n}"}

    def stk_query(self, checkout_request_id):
        if self.query_result is None:
            raise MpesaProcessing("The transaction is being processed")
        return self.query_result


@pytest.fixture
def mpesa():
    fake = FakeMpesa()
    app.dependency_overrides[get_mpesa_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mpesa_client, None)
    
@pytest.fixture(autouse=True)
def _verification_off_by_default(monkeypatch):
    # The security tests switch it back on. Everything else shouldn't need to verify emails.
    monkeypatch.setattr(settings, "require_email_verification", False)