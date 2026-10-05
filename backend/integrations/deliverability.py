"""Deliverability monitoring: re-check SPF/DKIM/DMARC per sending domain.

Cold-outreach mailboxes land in spam the moment their authentication records
regress — an SPF record edited past the 10-lookup limit, a DMARC policy reverted
to ``p=none``, a DKIM selector rotated away. This module reads those records over
DNS, grades the domain's posture, and compares it to the last known state so a
change ("drift") can be surfaced as a non-blocking alert.

All DNS access is defensive: lookups are time-boxed and every failure degrades to
an ``error``/``missing`` status rather than raising. Monitoring must never block
or crash the send path.
"""
import hashlib
import logging

import dns.resolver

logger = logging.getLogger(__name__)

# Short, bounded DNS access. A monitor that hangs is worse than one that reports
# an inconclusive "error" for a slow resolver.
_DNS_TIMEOUT = 3.0
_DNS_LIFETIME = 5.0

# DKIM has no discovery mechanism without the signing header, so we probe the
# selectors the major providers and ESPs actually use. A hit proves DKIM is
# published; a miss is reported as "unknown", never as a hard failure.
_COMMON_DKIM_SELECTORS = (
    'google', 'selector1', 'selector2', 'default', 'dkim', 'k1', 'k2',
    'mail', 's1', 's2', 'mandrill', 'mailjet', 'sendgrid', 'zoho', 'protonmail',
)


def _resolver():
    resolver = dns.resolver.Resolver()
    resolver.timeout = _DNS_TIMEOUT
    resolver.lifetime = _DNS_LIFETIME
    return resolver


def _txt_records(name):
    """Return the list of TXT strings at `name`, or None on lookup error.

    An empty list means the name resolved but held no TXT records (NXDOMAIN or
    NoAnswer); None means the lookup itself failed and the result is unknown.
    """
    try:
        answers = _resolver().resolve(name, 'TXT')
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except Exception as exc:  # noqa: BLE001 - any resolver error is non-fatal
        logger.info('TXT lookup failed for %s: %s', name, exc)
        return None

    records = []
    for rdata in answers:
        # dnspython splits long TXT values into chunks; join them back.
        parts = [p.decode('utf-8', 'ignore') if isinstance(p, bytes) else str(p) for p in rdata.strings]
        records.append(''.join(parts))
    return records


def _check_spf(domain):
    records = _txt_records(domain)
    if records is None:
        return {'spf_status': 'error', 'spf_record': ''}
    for record in records:
        if record.lower().startswith('v=spf1'):
            return {'spf_status': 'pass', 'spf_record': record.strip()}
    return {'spf_status': 'missing', 'spf_record': ''}


def _check_dmarc(domain):
    records = _txt_records(f'_dmarc.{domain}')
    if records is None:
        return {'dmarc_status': 'error', 'dmarc_policy': '', 'dmarc_record': ''}
    for record in records:
        if record.lower().startswith('v=dmarc1'):
            policy = ''
            for part in record.split(';'):
                key, _, value = part.strip().partition('=')
                if key.strip().lower() == 'p':
                    policy = value.strip().lower()
                    break
            return {'dmarc_status': 'pass', 'dmarc_policy': policy, 'dmarc_record': record.strip()}
    return {'dmarc_status': 'missing', 'dmarc_policy': '', 'dmarc_record': ''}


def _check_dkim(domain):
    found = []
    had_error = False
    for selector in _COMMON_DKIM_SELECTORS:
        records = _txt_records(f'{selector}._domainkey.{domain}')
        if records is None:
            had_error = True
            continue
        if any('v=dkim1' in r.lower() or 'p=' in r.lower() for r in records):
            found.append(selector)
    if found:
        return {'dkim_status': 'found', 'dkim_selectors': found}
    # No selector resolved. We cannot distinguish "no DKIM" from "custom
    # selector we did not probe", so this stays advisory ("unknown").
    return {'dkim_status': 'error' if had_error else 'unknown', 'dkim_selectors': []}


def _grade(result):
    """Derive an overall status and a human issue list from the three checks."""
    issues = []

    if result['spf_status'] == 'missing':
        issues.append('No SPF record found. Receiving servers cannot confirm your mail is authorised.')
    elif result['spf_status'] == 'error':
        issues.append('SPF record could not be read (DNS lookup failed).')

    if result['dmarc_status'] == 'missing':
        issues.append('No DMARC record. Add one (start with p=none) to monitor authentication.')
    elif result['dmarc_status'] == 'pass' and result['dmarc_policy'] in ('', 'none'):
        issues.append('DMARC policy is p=none. Move to quarantine or reject once SPF/DKIM are stable.')
    elif result['dmarc_status'] == 'error':
        issues.append('DMARC record could not be read (DNS lookup failed).')

    if result['dkim_status'] == 'unknown':
        issues.append('No DKIM signature detected on common selectors. Confirm DKIM is published.')

    spf_ok = result['spf_status'] == 'pass'
    dmarc_enforcing = result['dmarc_status'] == 'pass' and result['dmarc_policy'] in ('quarantine', 'reject')
    any_error = 'error' in (result['spf_status'], result['dmarc_status'], result['dkim_status'])

    if spf_ok and dmarc_enforcing and result['dkim_status'] == 'found':
        status = 'healthy'
    elif result['spf_status'] == 'missing' or result['dmarc_status'] == 'missing':
        status = 'failing'
    elif any_error:
        status = 'error'
    else:
        status = 'at_risk'

    return status, issues


def _fingerprint(result):
    """Stable hash of the authentication posture; drift is any change to it."""
    basis = '|'.join([
        result['spf_status'], result['spf_record'],
        result['dmarc_status'], result['dmarc_policy'], result['dmarc_record'],
        result['dkim_status'], ','.join(sorted(result['dkim_selectors'])),
    ])
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()


def check_domain(domain):
    """Run all three authentication checks for one domain. Never raises."""
    domain = (domain or '').strip().lower().rstrip('.')
    result = {
        'domain': domain,
        'spf_status': 'error', 'spf_record': '',
        'dkim_status': 'error', 'dkim_selectors': [],
        'dmarc_status': 'error', 'dmarc_policy': '', 'dmarc_record': '',
    }
    if not domain or '.' not in domain:
        result['status'], result['issues'] = 'error', ['Domain is not a valid sending domain.']
        result['fingerprint'] = ''
        return result

    try:
        result.update(_check_spf(domain))
        result.update(_check_dmarc(domain))
        result.update(_check_dkim(domain))
    except Exception as exc:  # noqa: BLE001 - monitoring must not crash
        logger.warning('Deliverability check crashed for %s: %s', domain, exc)

    result['status'], result['issues'] = _grade(result)
    result['fingerprint'] = _fingerprint(result)
    return result


def sending_domains(user):
    """Distinct domains this tenant actually sends from (connected mailboxes)."""
    from .models import EmailAccount

    domains = set()
    addresses = (
        EmailAccount.objects.filter(user=user, is_connected=True)
        .values_list('email_address', flat=True)
    )
    for address in addresses:
        if address and '@' in address:
            domain = address.rsplit('@', 1)[-1].strip().lower().rstrip('.')
            if domain:
                domains.add(domain)
    return sorted(domains)


def _describe_drift(previous, result):
    """Human summary of what changed between two checks of the same domain."""
    changes = []
    if previous.spf_status != result['spf_status']:
        changes.append(f"SPF {previous.spf_status} → {result['spf_status']}")
    if previous.dmarc_status != result['dmarc_status'] or previous.dmarc_policy != result['dmarc_policy']:
        was = previous.dmarc_policy or previous.dmarc_status
        now = result['dmarc_policy'] or result['dmarc_status']
        changes.append(f'DMARC {was} → {now}')
    if previous.dkim_status != result['dkim_status']:
        changes.append(f"DKIM {previous.dkim_status} → {result['dkim_status']}")
    return changes


def run_deliverability_monitor(user):
    """Re-check every sending domain for `user` and persist drift alerts.

    Returns the list of updated DomainDeliverability rows. A row's `has_alert`
    is raised when its DNS fingerprint changes from the previous check, or when
    the domain is in a non-healthy state for the first time.
    """
    from django.utils import timezone

    from .models import DomainDeliverability

    rows = []
    for domain in sending_domains(user):
        result = check_domain(domain)
        row, created = DomainDeliverability.objects.get_or_create(user=user, domain=domain)

        now = timezone.now()
        fingerprint_changed = bool(row.checked_at) and row.fingerprint != result['fingerprint']
        regressed = result['status'] in ('failing', 'at_risk')

        alert_message = ''
        if fingerprint_changed:
            changes = _describe_drift(row, result)
            summary = '; '.join(changes) if changes else 'authentication records changed'
            alert_message = f'Deliverability drift on {domain}: {summary}.'
        elif regressed:
            # First-ever check (or a still-unhealthy domain) with no clean baseline.
            alert_message = f'{domain} authentication is {result["status"].replace("_", " ")}: ' + (
                result['issues'][0] if result['issues'] else 'review SPF/DKIM/DMARC.'
            )

        if fingerprint_changed or (created and regressed):
            row.last_changed_at = now

        row.status = result['status']
        row.spf_status = result['spf_status']
        row.spf_record = result['spf_record']
        row.dkim_status = result['dkim_status']
        row.dkim_selectors = result['dkim_selectors']
        row.dmarc_status = result['dmarc_status']
        row.dmarc_policy = result['dmarc_policy']
        row.dmarc_record = result['dmarc_record']
        row.issues = result['issues']
        row.fingerprint = result['fingerprint']
        row.has_alert = bool(alert_message)
        row.alert_message = alert_message
        row.checked_at = now
        row.save()
        rows.append(row)

    return rows
