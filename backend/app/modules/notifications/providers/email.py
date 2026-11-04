import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings

from .base import PermanentSendError, SendError

log = logging.getLogger(__name__)


class ConsoleEmailSender:
    """Dev only: log the email instead of sending it."""

    def send(self, *, to: str, subject: str, text: str, html: str | None = None) -> str | None:
        log.info("EMAIL to=%s subject=%r\n%s", to, subject, text)
        return None


class SmtpEmailSender:
    def send(self, *, to: str, subject: str, text: str, html: str | None = None) -> str | None:
        try:
            msg = EmailMessage()
            msg["From"] = formataddr((settings.email_from_name, settings.email_from))
            msg["To"] = to
            msg["Subject"] = " ".join(subject.split())     # no line breaks in headers
            msg.set_content(text)
            if html:
                msg.add_alternative(html, subtype="html")
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            raise PermanentSendError(f"Recipient refused: {exc}") from exc
        except ValueError as exc:          # an address or header the email library rejects
            raise PermanentSendError(str(exc)) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise SendError(str(exc)) from exc
        return None