import io
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.modules.auth.models import Role, User

O = "/api/v1/organizer/events"
PROFILE = {
    "date_of_birth": "1990-05-14", "gender": "female", "phone": "0712345678", "tshirt_size": "M",
    "emergency_contact_name": "Mary Kamau", "emergency_contact_phone": "0722000111",
    "emergency_contact_relationship": "Sister",
}


@pytest.fixture(autouse=True)
def media(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    return tmp_path


def signup(c, email, name="Test User"):
    res = c.post("/api/v1/auth/signup", json={"full_name": name, "email": email, "password": "correct-horse-1"})
    assert res.status_code == 201
    assert c.put("/api/v1/runners/me", json=PROFILE).status_code == 200


def promote(db, email, role):
    db.scalars(select(User).where(User.email == email)).first().role = role
    db.commit()


def organizer(db, email="org@example.com", role=Role.organizer):
    c = TestClient(app)
    signup(c, email)
    promote(db, email, role)
    return c


def new_event(c):
    today = date.today()
    res = c.post(O, json={
        "name": "Lake Run", "event_date": (today + timedelta(days=60)).isoformat(), "location": "Nakuru",
        "registration_opens": (today - timedelta(days=1)).isoformat(),
        "registration_closes": (today + timedelta(days=50)).isoformat(),
        "distances": [{"name": "5K", "km": 5, "fee": 500, "capacity": 5}],
    })
    assert res.status_code == 201, res.text
    return res.json()["id"]


def image_bytes(fmt="PNG", size=(1600, 900), exif=False):
    out = io.BytesIO()
    kwargs = {}
    if exif:
        tags = Image.Exif()
        tags[0x010F] = "SecretCamera"
        kwargs["exif"] = tags.tobytes()
    Image.new("RGB", size, (30, 120, 90)).save(out, fmt, **kwargs)
    return out.getvalue()


def upload(c, event_id, data, name="banner.png", ctype="image/png"):
    return c.post(f"{O}/{event_id}/banner", files={"file": (name, data, ctype)})


def code(res):
    return res.json()["detail"]["code"]


def test_upload_creates_a_resized_banner_and_a_share_image(client, db, media):
    org = organizer(db)
    event_id = new_event(org)
    res = upload(org, event_id, image_bytes(size=(3000, 2000)))
    assert res.status_code == 200
    url = res.json()["banner_url"]
    assert url.startswith("/media/events/") and url.endswith(".jpg")
    key = Path(url).stem
    banner = Image.open(media / "events" / f"{key}.jpg")
    share = Image.open(media / "events" / f"{key}-og.jpg")
    assert banner.format == "JPEG" and max(banner.size) == 1600
    assert share.format == "JPEG" and share.size == (1200, 630)


def test_upload_strips_metadata(client, db, media):
    org = organizer(db)
    event_id = new_event(org)
    res = upload(org, event_id, image_bytes("JPEG", exif=True), "photo.jpg", "image/jpeg")
    assert res.status_code == 200
    key = Path(res.json()["banner_url"]).stem
    for name in (f"{key}.jpg", f"{key}-og.jpg"):
        raw = (media / "events" / name).read_bytes()
        assert b"SecretCamera" not in raw
        assert len(Image.open(io.BytesIO(raw)).getexif()) == 0


def test_non_images_are_rejected(client, db):
    org = organizer(db)
    event_id = new_event(org)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    for name, data, ctype in [
        ("a.jpg", b"just some text", "image/jpeg"),
        ("a.svg", svg, "image/svg+xml"),
        ("a.png", image_bytes()[:50], "image/png"),
    ]:
        res = upload(org, event_id, data, name, ctype)
        assert res.status_code == 422 and code(res) == "invalid_image", name
    assert org.get(f"{O}/{event_id}").json()["banner_url"] is None


def test_tiny_and_oversized_files_are_rejected(client, db, monkeypatch):
    org = organizer(db)
    event_id = new_event(org)
    res = upload(org, event_id, image_bytes(size=(100, 100)))
    assert res.status_code == 422 and code(res) == "invalid_image"
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    res = upload(org, event_id, b"0" * (1024 * 1024 + 10))
    assert res.status_code == 413 and code(res) == "image_too_large"


def test_replacing_a_banner_removes_the_old_files(client, db, media):
    org = organizer(db)
    event_id = new_event(org)
    first = upload(org, event_id, image_bytes()).json()["banner_url"]
    second = upload(org, event_id, image_bytes(size=(1400, 800))).json()["banner_url"]
    assert first != second
    names = sorted(p.name for p in (media / "events").iterdir())
    assert names == sorted([Path(second).name, Path(second).stem + "-og.jpg"])


def test_deleting_a_banner_removes_the_files(client, db, media):
    org = organizer(db)
    event_id = new_event(org)
    upload(org, event_id, image_bytes())
    res = org.delete(f"{O}/{event_id}/banner")
    assert res.status_code == 200 and res.json()["banner_url"] is None
    assert list((media / "events").iterdir()) == []


def test_only_the_owner_can_change_the_banner(client, db):
    owner = organizer(db)
    event_id = new_event(owner)
    other = organizer(db, "other@example.com")
    assert upload(other, event_id, image_bytes()).status_code == 404
    assert other.delete(f"{O}/{event_id}/banner").status_code == 404
    signup(client, "runner@example.com")
    assert upload(client, event_id, image_bytes()).status_code == 403
    assert upload(TestClient(app), event_id, image_bytes()).status_code == 401


def test_deleting_an_event_removes_its_banner_files(client, db, media):
    org = organizer(db)
    event_id = new_event(org)
    upload(org, event_id, image_bytes())
    assert org.delete(f"{O}/{event_id}").status_code == 204
    assert list((media / "events").iterdir()) == []