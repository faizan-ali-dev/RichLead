"""Funnel analytics grouped by campaign and by sending mailbox.

Aggregate reply performance so a weak campaign or a struggling inbox is visible
before it drags down the whole book. Metrics come from the event timestamps
(`first_sent_at`, `replied_at`) rather than the mutable `status`, so a lead that
replied is still counted as sent.

Bounce is reported from `email_status` where the provider marked an address
unverified; a dedicated bounce pipeline (parsing DSNs) is a separate feature and
would make this column exact.
"""
from django.db.models import Count, Q

from .models import Lead


def _reply_rate(replied, sent):
    return round(replied / sent, 4) if sent else 0.0


def _funnel_row(label, total, sent, replied):
    return {
        'label': label or 'Uncategorized',
        'total': total,
        'sent': sent,
        'replied': replied,
        'pending': total - sent,
        'reply_rate': _reply_rate(replied, sent),
    }


def campaign_funnels(user):
    """Per-campaign funnel. Groups by `campaign`, falling back to `source`."""
    rows = (
        Lead.objects.filter(user=user)
        .values('campaign', 'source')
        .annotate(
            total=Count('id'),
            sent=Count('id', filter=Q(first_sent_at__isnull=False)),
            replied=Count('id', filter=Q(replied_at__isnull=False)),
        )
    )

    # Collapse (campaign, source) into a single label per campaign-or-source.
    grouped = {}
    for row in rows:
        label = row['campaign'] or row['source'] or 'Uncategorized'
        bucket = grouped.setdefault(label, {'total': 0, 'sent': 0, 'replied': 0})
        bucket['total'] += row['total']
        bucket['sent'] += row['sent']
        bucket['replied'] += row['replied']

    funnels = [_funnel_row(label, b['total'], b['sent'], b['replied']) for label, b in grouped.items()]
    funnels.sort(key=lambda f: (-f['sent'], f['label']))
    return funnels


def mailbox_funnels(user):
    """Per-sending-mailbox funnel.

    A lead's sending mailbox is the account its first outbound message went from.
    Reply rate per mailbox surfaces an inbox whose deliverability is slipping.
    """
    from inbox.models import EmailMessage
    from integrations.models import EmailAccount

    # First outbound message per lead -> which account sent the first touch.
    first_touch = {}
    outbound = (
        EmailMessage.objects.filter(user=user, direction='outbound', lead__isnull=False)
        .exclude(account__isnull=True)
        .order_by('lead_id', 'received_at', 'id')
        .values('lead_id', 'account_id')
    )
    for row in outbound:
        first_touch.setdefault(row['lead_id'], row['account_id'])

    if not first_touch:
        return []

    # Which of those leads replied.
    replied_leads = set(
        Lead.objects.filter(user=user, id__in=first_touch, replied_at__isnull=False)
        .values_list('id', flat=True)
    )

    per_account = {}
    for lead_id, account_id in first_touch.items():
        bucket = per_account.setdefault(account_id, {'sent': 0, 'replied': 0})
        bucket['sent'] += 1
        if lead_id in replied_leads:
            bucket['replied'] += 1

    emails = dict(
        EmailAccount.objects.filter(user=user, id__in=per_account)
        .values_list('id', 'email_address')
    )

    funnels = []
    for account_id, b in per_account.items():
        funnels.append({
            'label': emails.get(account_id, 'Removed mailbox'),
            'sent': b['sent'],
            'replied': b['replied'],
            'reply_rate': _reply_rate(b['replied'], b['sent']),
        })
    funnels.sort(key=lambda f: (-f['sent'], f['label']))
    return funnels


def analytics_overview(user):
    return {
        'campaigns': campaign_funnels(user),
        'mailboxes': mailbox_funnels(user),
    }
