"""Safe HTML subset for displaying untrusted email bodies in the authenticated UI."""
import bleach


EMAIL_TAGS = frozenset({
    'a', 'b', 'blockquote', 'br', 'caption', 'code', 'dd', 'div', 'dl', 'dt',
    'em', 'h1', 'h2', 'h3', 'h4', 'hr', 'i', 'li', 'ol', 'p', 'pre', 'small',
    'span', 'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'th', 'thead',
    'tr', 'u', 'ul',
})
EMAIL_ATTRIBUTES = {
    'a': ['href', 'title'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
}


def sanitize_email_html(value):
    if not value:
        return value
    return bleach.clean(
        value,
        tags=EMAIL_TAGS,
        attributes=EMAIL_ATTRIBUTES,
        protocols={'http', 'https', 'mailto'},
        strip=True,
        strip_comments=True,
    )
