import re

import sentry_sdk

from app.core.config import settings

_SECRET_IN_URL = re.compile(r"(/callbacks/stk/)[^/?#]+")


def _scrub(event, hint):
    """The M-Pesa callback URL contains a secret. It must never reach a third-party service."""
    request = event.get("request") or {}
    if isinstance(request.get("url"), str):
        request["url"] = _SECRET_IN_URL.sub(r"\1[redacted]", request["url"])
    if isinstance(event.get("transaction"), str):
        event["transaction"] = _SECRET_IN_URL.sub(r"\1[redacted]", event["transaction"])
    return event


def init_sentry(service: str) -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,            # no cookies, user details or IP addresses
        max_request_body_size="never",     # request bodies can hold passwords and medical notes
        include_local_variables=False,     # so can the local variables of a crashing function
        traces_sample_rate=0.0,
        before_send=_scrub,
    )
    sentry_sdk.set_tag("service", service)