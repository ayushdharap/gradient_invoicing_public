from datetime import datetime, timezone

def iso_today() -> str:
    """Return today's date (YYYY-MM-DD) in UTC."""
    return datetime.now(timezone.utc).date().isoformat()

def month_key(date_str: str) -> str:
    """2025-03-24 → '2025-03'  (year-month bucket)."""
    return date_str[:7]

def month_label(date_str: str) -> str:
    """2025-03-24 → 'Mar 2025'."""
    dt = datetime.fromisoformat(date_str)
    return dt.strftime("%b %Y")
