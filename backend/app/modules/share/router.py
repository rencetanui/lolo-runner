import html
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.events.models import Event, EventStatus

router = APIRouter(tags=["Share"], include_in_schema=False)


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def render(event: Event) -> str:
    e = lambda s: html.escape(s, quote=True)
    base = settings.frontend_url.rstrip("/")
    share_url = f"{base}/share/e/{event.id}"
    when = event.event_date.strftime("%a %d %b %Y")
    cancelled = event.status == EventStatus.cancelled
    title = f"{'Cancelled: ' if cancelled else ''}{event.name}"
    summary = f"{when} · {event.location}"
    if event.description:
        summary += " — " + _clip(event.description, 150)
    image = f"{base}/media/events/{event.banner_file}-og.jpg" if event.banner_file else f"{base}/og-image.png"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{e(title)}</title>
<meta name="description" content="{e(summary)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(settings.app_name)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(summary)}">
<meta property="og:url" content="{e(share_url)}">
<meta property="og:image" content="{e(image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0;url=/events/{event.id}">
</head><body>
<p><a href="/events/{event.id}">{e(title)}</a></p>
<script>location.replace("/events/{event.id}")</script>
</body></html>"""


@router.get("/share/e/{event_id}", response_class=HTMLResponse)
def share_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None or event.status not in (EventStatus.published, EventStatus.cancelled):
        raise HTTPException(404, "Event not found")      # drafts must not leak their titles
    return HTMLResponse(render(event), headers={"Cache-Control": "public, max-age=300"})