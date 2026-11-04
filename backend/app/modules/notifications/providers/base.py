class SendError(Exception):
    """A temporary failure. Worth retrying."""


class PermanentSendError(SendError):
    """Retrying will never help (for example, the recipient doesn't exist)."""