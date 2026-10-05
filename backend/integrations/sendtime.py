"""Send-time optimization.

Cold email opened in the recipient's morning gets read far more often than mail
that lands overnight. This module infers a recipient's timezone from their
location and computes the next sending slot inside the tenant's configured window
(business hours, weekdays), expressed in that recipient's local time.

Timezone inference is deliberately coarse and dependency-free: there is no
reliable city-to-tz lookup in the stdlib, and a rough region match ("the US
Eastern-ish morning") is enough to avoid the real failure mode, which is sending
at 3am local. When location is unknown we fall back to the tenant's own timezone.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = ZoneInfo('UTC')

# Keyword -> IANA timezone. Ordered longest-first at match time so "new york"
# wins over "york". Representative, not exhaustive: the goal is the right morning,
# not the exact municipality.
_LOCATION_TIMEZONES = {
    # United States (pick a representative zone per region)
    'new york': 'America/New_York', 'nyc': 'America/New_York',
    'boston': 'America/New_York', 'washington': 'America/New_York',
    'atlanta': 'America/New_York', 'miami': 'America/New_York',
    'chicago': 'America/Chicago', 'austin': 'America/Chicago',
    'dallas': 'America/Chicago', 'houston': 'America/Chicago',
    'denver': 'America/Denver', 'phoenix': 'America/Phoenix',
    'los angeles': 'America/Los_Angeles', 'san francisco': 'America/Los_Angeles',
    'seattle': 'America/Los_Angeles', 'san diego': 'America/Los_Angeles',
    'bay area': 'America/Los_Angeles', 'silicon valley': 'America/Los_Angeles',
    'united states': 'America/New_York', 'usa': 'America/New_York', 'u.s.': 'America/New_York',
    # Canada
    'toronto': 'America/Toronto', 'canada': 'America/Toronto',
    'vancouver': 'America/Vancouver',
    # UK & Ireland
    'london': 'Europe/London', 'united kingdom': 'Europe/London',
    'uk': 'Europe/London', 'england': 'Europe/London', 'ireland': 'Europe/Dublin',
    'dublin': 'Europe/Dublin',
    # Europe
    'paris': 'Europe/Paris', 'france': 'Europe/Paris',
    'berlin': 'Europe/Berlin', 'germany': 'Europe/Berlin', 'munich': 'Europe/Berlin',
    'amsterdam': 'Europe/Amsterdam', 'netherlands': 'Europe/Amsterdam',
    'madrid': 'Europe/Madrid', 'spain': 'Europe/Madrid',
    'stockholm': 'Europe/Stockholm', 'sweden': 'Europe/Stockholm',
    # Asia-Pacific
    'india': 'Asia/Kolkata', 'bangalore': 'Asia/Kolkata', 'bengaluru': 'Asia/Kolkata',
    'mumbai': 'Asia/Kolkata', 'delhi': 'Asia/Kolkata',
    'singapore': 'Asia/Singapore', 'dubai': 'Asia/Dubai', 'uae': 'Asia/Dubai',
    'sydney': 'Australia/Sydney', 'australia': 'Australia/Sydney',
    'melbourne': 'Australia/Melbourne',
    'tokyo': 'Asia/Tokyo', 'japan': 'Asia/Tokyo',
}


def infer_timezone(location, default='UTC'):
    """Best-effort IANA timezone for a free-text location. Falls back to `default`."""
    text = (location or '').strip().lower()
    if text:
        # Longest keyword first so "new york" beats "york".
        for keyword in sorted(_LOCATION_TIMEZONES, key=len, reverse=True):
            if keyword in text:
                return ZoneInfo(_LOCATION_TIMEZONES[keyword])
    try:
        return ZoneInfo(default)
    except ZoneInfoNotFoundError:
        return UTC


def next_send_time(window, tz, *, now=None):
    """Next instant inside the window, in `tz`, as an aware UTC datetime.

    `window` is anything with `earliest_hour`, `latest_hour`, `weekdays_only`.
    If `now` is already inside today's window, returns `now` (send immediately).
    Otherwise advances to the next window opening, skipping weekends when asked.
    """
    now = now or datetime.now(UTC)
    local = now.astimezone(tz)

    earliest = int(window.earliest_hour)
    latest = int(window.latest_hour)

    def opening_on(day):
        return datetime.combine(day, time(hour=earliest), tzinfo=tz)

    def is_working_day(day):
        return not window.weekdays_only or day.weekday() < 5  # Mon-Fri

    # Inside today's window on a working day -> go now.
    if is_working_day(local.date()) and earliest <= local.hour < latest:
        return now

    # Before today's opening on a working day -> wait for the opening.
    candidate_day = local.date()
    if is_working_day(candidate_day) and local.hour < earliest:
        return opening_on(candidate_day).astimezone(UTC)

    # Otherwise roll forward to the next working day's opening.
    for _ in range(8):
        candidate_day = candidate_day + timedelta(days=1)
        if is_working_day(candidate_day):
            return opening_on(candidate_day).astimezone(UTC)

    return now  # unreachable given a <=7-day search, but fail open to "now"
