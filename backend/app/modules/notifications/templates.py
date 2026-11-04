import html
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.config import settings


@dataclass
class Rendered:
    subject: str
    text: str
    html: str
    sms: str | None = None      # None means "no SMS for this message"


def fmt_date(d: date) -> str:
    return d.strftime("%a %d %b %Y")


def _first(name: str) -> str:
    parts = name.split()
    return parts[0] if parts else "there"


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "."


def _sms(text: str) -> str:
    """Plain ASCII keeps an SMS in one cheap segment. Accents are dropped, not mangled."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()[:300]


def _page(title: str, paragraphs: list[str], button: tuple[str, str] | None = None) -> str:
    """Every piece of text is escaped, so organizer- and runner-entered values can't inject HTML."""
    e = html.escape
    body = "".join(f'<p style="margin:0 0 12px">{e(p)}</p>' for p in paragraphs)
    cta = ""
    if button:
        label, url = button
        cta = (
            f'<p style="margin:20px 0"><a href="{e(url, quote=True)}" '
            'style="background:#111;color:#fff;padding:10px 18px;border-radius:6px;'
            f'text-decoration:none">{e(label)}</a></p>'
        )
    return (
        '<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:16px;color:#111">'
        f'<h2 style="margin:0 0 16px">{e(title)}</h2>{body}{cta}'
        f'<p style="color:#666;font-size:12px;margin-top:28px">{e(settings.app_name)}</p></div>'
    )


def registration_confirmed(
    *, name: str, event_name: str, event_date: date, location: str, distance: str,
    bib: int, url: str, amount: Decimal | None = None, receipt: str | None = None,
) -> Rendered:
    first = _first(name)
    lines = [
        f"Event: {event_name}",
        f"Date: {fmt_date(event_date)}",
        f"Location: {location}",
        f"Distance: {distance}",
        f"Bib number: {bib}",
    ]
    if amount is not None:
        paid = f"Payment received: KES {int(amount):,}"
        if receipt:
            paid += f" (M-Pesa ref {receipt})"
        lines.append(paid)
    intro = f"Hi {first}, you're in! Your registration is confirmed."
    outro = "Keep this message: it has your bib number."
    return Rendered(
        subject=f"You're in: {event_name}",
        text="\n".join([intro, "", *lines, "", outro, "", f"View your registration: {url}"]),
        html=_page("Registration confirmed", [intro, *lines, outro], ("View registration", url)),
        sms=_sms(
            f"{settings.app_name}: confirmed! {_clip(event_name, 40)} {distance}, "
            f"{fmt_date(event_date)}. Bib {bib}."
        ),
    )


def registration_cancelled(*, name: str, event_name: str, distance: str, url: str) -> Rendered:
    first = _first(name)
    intro = f"Hi {first}, your registration for {event_name} ({distance}) has been cancelled."
    note = "If you had already paid, please contact the organizers about a refund."
    again = "Changed your mind? You can register again while registration is open."
    return Rendered(
        subject=f"Registration cancelled: {event_name}",
        text="\n".join([intro, "", note, again, "", f"Event page: {url}"]),
        html=_page("Registration cancelled", [intro, note, again], ("View event", url)),
        sms=None,      # email only: no SMS cost for a cancellation
    )


def event_changed(*, name: str, event_name: str, changes: list[tuple[str, str, str]], url: str) -> Rendered:
    first = _first(name)
    intro = f"Hi {first}, the organizers have updated {event_name}."
    lines = [f"{label}: {old} -> {new}" for label, old, new in changes]
    note = (
        "Your registration and bib number are unchanged. "
        "If you can no longer make it, you can cancel from your account."
    )
    return Rendered(
        subject=f"Update: {event_name}",
        text="\n".join([intro, "", *lines, "", note, "", f"Details: {url}"]),
        html=_page("Event update", [intro, *lines, note], ("View registration", url)),
        sms=_sms(
            f"{settings.app_name}: {_clip(event_name, 40)} updated. "
            + " ".join(f"{label} is now {new}." for label, _old, new in changes)
        ),
    )


def event_reminder(
    *, name: str, event_name: str, event_date: date, location: str, distance: str, bib: int, url: str,
) -> Rendered:
    first = _first(name)
    intro = f"Hi {first}, {event_name} is tomorrow. Good luck!"
    lines = [
        f"Date: {fmt_date(event_date)}",
        f"Location: {location}",
        f"Distance: {distance}",
        f"Bib number: {bib}",
    ]
    return Rendered(
        subject=f"Tomorrow: {event_name}",
        text="\n".join([intro, "", *lines, "", f"Your registration: {url}"]),
        html=_page("See you tomorrow", [intro, *lines], ("View registration", url)),
        sms=_sms(
            f"{settings.app_name}: {_clip(event_name, 40)} is tomorrow at {_clip(location, 30)}. "
            f"{distance}, bib {bib}. Good luck!"
        ),
    )

def email_verification(*, name: str, url: str, hours: int) -> Rendered:
    intro = f"Hi {_first(name)}, please confirm your email address to finish setting up your {settings.app_name} account."
    note = f"This link works for {hours} hours. If you didn't create an account, you can ignore this email."
    return Rendered(
        subject="Confirm your email address",
        text="\n".join([intro, "", f"Confirm your email: {url}", "", note]),
        html=_page("Confirm your email", [intro, note], ("Confirm email address", url)),
    )


def password_reset(*, name: str, url: str, minutes: int) -> Rendered:
    intro = f"Hi {_first(name)}, we received a request to reset your {settings.app_name} password."
    note = (
        f"This link works once and expires in {minutes} minutes. If you didn't ask for this, "
        "ignore this email and your password will stay the same."
    )
    return Rendered(
        subject="Reset your password",
        text="\n".join([intro, "", f"Choose a new password: {url}", "", note]),
        html=_page("Reset your password", [intro, note], ("Choose a new password", url)),
    )


def password_changed(*, name: str, url: str) -> Rendered:
    intro = f"Hi {_first(name)}, the password on your {settings.app_name} account was just changed."
    note = (
        "If that was you, there's nothing more to do. If it wasn't, reset your password "
        "straight away and contact the organizers."
    )
    return Rendered(
        subject="Your password was changed",
        text="\n".join([intro, "", note, "", f"Reset your password: {url}"]),
        html=_page("Password changed", [intro, note], ("Reset your password", url)),
    )