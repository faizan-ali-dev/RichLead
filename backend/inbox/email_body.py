"""Display helpers for trimming quoted history from inbound email replies."""
import re


_QUOTE_BOUNDARIES = (
    re.compile(r'(?im)^\s*[-_]{2,}\s*(?:original|forwarded) message\s*[-_]{0,}\s*$'),
    re.compile(r'(?im)^\s*begin forwarded message\s*:\s*$'),
    re.compile(r'(?im)(?<!\S)On[ \t]+[^\n]{1,300}?\bwrote:[ \t]*'),
    re.compile(r'(?im)^\s*From:\s*.+(?:\n\s*(?:Sent|Date|To|Cc|Subject):\s*.+){2,5}\s*$'),
    re.compile(r'(?m)^\s*_{10,}\s*$'),
    re.compile(r'(?m)^\s*>'),
)


def strip_quoted_reply(value):
    """Return only the new reply, retaining content before common quote markers.

    This is deliberately display-time cleanup. The original provider body stays
    in the database, so no imported email content is lost.
    """
    body = (value or '').replace('\r\n', '\n').replace('\r', '\n').replace('\xa0', ' ')
    boundaries = [match.start() for pattern in _QUOTE_BOUNDARIES if (match := pattern.search(body))]
    if boundaries:
        body = body[:min(boundaries)]
    return '\n'.join(line.rstrip() for line in body.splitlines()).strip()


def reply_preview(value, limit=120):
    """Create a compact single-line excerpt for the "Replied to" hint."""
    preview = ' '.join(strip_quoted_reply(value).split())
    if len(preview) <= limit:
        return preview
    shortened = preview[:limit - 1].rsplit(' ', 1)[0].rstrip()
    return f'{shortened or preview[:limit - 1].rstrip()}…'
