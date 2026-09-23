import re
from datetime import datetime

_FRACTIONAL_SECONDS_RE = re.compile(r"\.(\d+)")


def parse_iso_dt(value: str) -> datetime:
    """Parse an ISO-8601 timestamp coming from Postgres/PostgREST, which
    trims trailing zeros off the fractional-seconds component (e.g.
    ".7744" instead of ".774400") — Python's datetime.fromisoformat()
    before 3.11 only accepts exactly 0, 3, or 6 fractional digits and
    raises ValueError on anything else. Pad/truncate to 6 (microseconds)
    so any precision parses reliably, regardless of Python version."""
    value = value.replace("Z", "+00:00")
    value = _FRACTIONAL_SECONDS_RE.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), value, count=1)
    return datetime.fromisoformat(value)
