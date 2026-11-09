import uuid

from app.core.config import settings
from app.modules.events.models import EventStatus


def test_share_page_carries_event_specific_preview_tags(client, make_event, db):
    event = make_event(name="Lake Milford Charity Run")
    event.description = "A scenic run around the lake."
    event.banner_file = "abc123"
    db.commit()
    res = client.get(f"/share/e/{event.id}")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/html")
    page = res.text
    base = settings.frontend_url.rstrip("/")
    assert '<meta property="og:title" content="Lake Milford Charity Run">' in page
    assert "A scenic run around the lake." in page
    assert f'content="{base}/media/events/abc123-og.jpg"' in page
    assert f'/share/e/{event.id}"' in page              # og:url is the share link itself
    assert f"/events/{event.id}" in page                # people are sent on to the real page


def test_share_page_escapes_everything_an_organizer_typed(client, make_event, db):
    event = make_event(name='"><script>alert(1)</script>')
    event.description = "<img src=x onerror=alert(1)>"
    db.commit()
    page = client.get(f"/share/e/{event.id}").text
    assert "<script>alert(1)</script>" not in page and "<img src=x" not in page
    assert "&lt;script&gt;" in page


def test_drafts_and_unknown_events_have_no_share_page(client, make_event, db):
    event = make_event()
    event.status = EventStatus.draft
    db.commit()
    assert client.get(f"/share/e/{event.id}").status_code == 404
    assert client.get(f"/share/e/{uuid.uuid4()}").status_code == 404


def test_cancelled_events_say_so_in_the_preview(client, make_event, db):
    event = make_event()
    event.status = EventStatus.cancelled
    db.commit()
    assert 'content="Cancelled: ' in client.get(f"/share/e/{event.id}").text


def test_events_without_a_banner_use_the_default_image(client, make_event):
    event = make_event()
    page = client.get(f"/share/e/{event.id}").text
    assert f'{settings.frontend_url.rstrip("/")}/og-image.png' in page