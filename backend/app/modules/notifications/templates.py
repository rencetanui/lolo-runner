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


def _money(amount) -> str:
    return f"KES {int(amount):,}"


def _mask(phone: str) -> str:
    return phone if len(phone) <= 7 else phone[:4] + "*" * (len(phone) - 7) + phone[-3:]


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
    logo = ""
    if settings.frontend_url.startswith("https://"):      # a localhost image can't load in a real inbox
        logo = (
            f'<img src="{e(settings.frontend_url.rstrip("/"))}/logo.png" alt="{e(settings.app_name)}" '
            'height="40" style="display:block;margin:0 0 20px">'
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


def registration_cancelled(
    *, name: str, event_name: str, distance: str, url: str,
    refund_amount=None, refund_phone: str | None = None, no_refund: bool = False,
) -> Rendered:
    first = _first(name)
    intro = f"Hi {first}, your registration for {event_name} ({distance}) has been cancelled."
    notes: list[str] = []
    if refund_amount is not None:
        notes.append(
            f"A refund of {_money(refund_amount)} has been requested. It will be sent to the M-Pesa number "
            f"you paid from ({_mask(refund_phone or '')}), and we'll email you when it's on its way."
        )
    elif no_refund:
        notes.append("The refund period for this event had ended, so your entry fee isn't refundable.")
    again = "Changed your mind? You can register again while registration is open."
    return Rendered(
        subject=f"Registration cancelled: {event_name}",
        text="\n".join([intro, "", *notes, again, "", f"Event page: {url}"]),
        html=_page("Registration cancelled", [intro, *notes, again], ("View event", url)),
        sms=None,      # email only: no SMS cost for a cancellation
    )
def refund_requested(*, name: str, event_name: str, amount, phone: str, url: str) -> Rendered:
    intro = f"Hi {_first(name)}, we've started a refund of {_money(amount)} for {event_name}."
    note = (
        f"It will be sent to the M-Pesa number you paid from ({_mask(phone)}). "
        "We'll email and text you when it's on its way."
    )
    return Rendered(
        subject=f"Refund requested: {event_name}",
        text="\n".join([intro, "", note, "", f"Details: {url}"]),
        html=_page("Refund requested", [intro, note], ("View details", url)),
    )


def refund_paid(*, name: str, event_name: str, amount, phone: str, reference: str, url: str) -> Rendered:
    intro = f"Hi {_first(name)}, your refund of {_money(amount)} for {event_name} has been sent."
    lines = [f"Sent to: {_mask(phone)}", f"M-Pesa reference: {reference}"]
    return Rendered(
        subject=f"Refund sent: {event_name}",
        text="\n".join([intro, "", *lines, "", f"Details: {url}"]),
        html=_page("Refund sent", [intro, *lines], ("View details", url)),
        sms=_sms(
            f"{settings.app_name}: refund of {_money(amount)} sent to {_mask(phone)} for "
            f"{_clip(event_name, 40)}. M-Pesa ref {reference}."
        ),
    )


def refund_rejected(*, name: str, event_name: str, amount, reason: str, url: str) -> Rendered:
    intro = f"Hi {_first(name)}, we couldn't approve the refund of {_money(amount)} for {event_name}."
    why = f"Reason: {reason}"
    note = "If you think this is a mistake, please contact the organizers."
    return Rendered(
        subject=f"Refund not approved: {event_name}",
        text="\n".join([intro, "", why, note, "", f"Details: {url}"]),
        html=_page("Refund not approved", [intro, why, note], ("View details", url)),
    )


def event_cancelled(
    *, name: str, event_name: str, event_date: date, reason: str,
    refund_amount, refund_phone: str | None, url: str,
) -> Rendered:
    intro = f"Hi {_first(name)}, we're sorry to tell you that {event_name} on {fmt_date(event_date)} has been cancelled by the organizers."
    lines = [f"Reason: {reason}"] if reason else []
    sms_text = f"{settings.app_name}: {_clip(event_name, 40)} on {fmt_date(event_date)} is cancelled."
    if refund_amount is not None:
        refund = (
            f"Your entry fee of {_money(refund_amount)} will be refunded in full to the M-Pesa number you paid "
            f"from ({_mask(refund_phone or '')}). We'll message you when it's sent."
        )
        lines.append(refund)
        sms_text += f" {_money(refund_amount)} refund coming to {_mask(refund_phone or '')}."
    return Rendered(
        subject=f"Event cancelled: {event_name}",
        text="\n".join([intro, "", *lines, "", f"Details: {url}"]),
        html=_page("Event cancelled", [intro, *lines], ("View details", url)),
        sms=_sms(sms_text),
    )


def refunds_queued_alert(*, event_name: str, count: int, total, url: str) -> Rendered:
    title = "Refunds to send"
    lines = [f"Event: {event_name}", f"Refunds: {count}", f"Total: {_money(total)}"]
    return Rendered(
        subject=f"{count} refund(s) to send: {event_name}",
        text="\n".join([title, "", *lines, "", f"Open the queue: {url}"]),
        html=_page(title, lines, ("Open refunds", url)),
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
    
def google_linked(*, name: str, url: str) -> Rendered:
    intro = f"Hi {_first(name)}, Google sign-in was just added to your {settings.app_name} account."
    note = (
        "If that was you, there's nothing more to do. If it wasn't, reset your password "
        "straight away and contact the organizers."
    )
    return Rendered(
        subject="Google sign-in added to your account",
        text="\n".join([intro, "", note, "", f"Reset your password: {url}"]),
        html=_page("Google sign-in added", [intro, note], ("Reset your password", url)),
    )
    
def payment_alert(*, kind: str, amount: Decimal, receipt: str | None, reason: str, url: str) -> Rendered:
    title = {
        "needs_review": "A payment needs review",
        "needs_refund": "A payment needs a refund",
    }.get(kind, "A payment needs attention")
    lines = [f"Amount: KES {int(amount):,}"]
    if receipt:
        lines.append(f"M-Pesa reference: {receipt}")
    lines.append(f"Reason: {reason}")
    return Rendered(
        subject=f"{title}: KES {int(amount):,}",
        text="\n".join([title, "", *lines, "", f"Open it: {url}"]),
        html=_page(title, lines, ("Open in admin", url)),
    )