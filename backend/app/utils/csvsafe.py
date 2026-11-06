def csv_safe(value) -> str:
    """Stop spreadsheet apps from running user-entered text as a formula."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s