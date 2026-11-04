from app.core.config import settings

from .email import ConsoleEmailSender, SmtpEmailSender
from .sms import AfricasTalkingSender, ConsoleSmsSender


def get_email_sender():
    return SmtpEmailSender() if settings.email_backend == "smtp" else ConsoleEmailSender()


def get_sms_sender():
    return AfricasTalkingSender() if settings.sms_backend == "africastalking" else ConsoleSmsSender()