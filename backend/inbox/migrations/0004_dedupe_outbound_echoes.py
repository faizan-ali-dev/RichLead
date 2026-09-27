"""Remove the duplicate outbound copies already stored.

Before rfc_message_id existed, a sent email was written once at send time under a
synthetic `sent-<uuid>` id and then written again by the next mailbox sync under
the provider's own id. Threads therefore showed the same message twice, the
second copy often truncated (Graph's bodyPreview).

Keeps the copy written at send time: it holds the exact body that was delivered,
whereas the synced copy may be a truncated, HTML-escaped preview.
"""
from django.db import migrations


def drop_duplicate_outbound(apps, schema_editor):
    EmailMessage = apps.get_model('inbox', 'EmailMessage')

    seen = {}
    removed = 0

    outbound = (
        EmailMessage.objects
        .filter(direction='outbound')
        .order_by('user_id', 'lead_id', 'received_at', 'id')
    )

    for message in outbound.iterator():
        if message.lead_id is None:
            continue

        # Same tenant, same lead, same subject, same minute == the same send.
        key = (
            message.user_id,
            message.lead_id,
            (message.subject or '').strip().lower(),
            message.received_at.replace(second=0, microsecond=0) if message.received_at else None,
        )

        first = seen.get(key)
        if first is None:
            seen[key] = message
            continue

        # Prefer whichever copy has the longer body: the synced copy is often a
        # truncated preview, and truncation is the thing we want to discard.
        keep, drop = (first, message)
        if len(message.body_text or '') > len(first.body_text or ''):
            keep, drop = message, first
            seen[key] = message

        drop.delete()
        removed += 1

    if removed:
        print(f'  removed {removed} duplicate outbound message(s)')


class Migration(migrations.Migration):

    dependencies = [
        ('inbox', '0003_emailmessage_rfc_message_id'),
    ]

    operations = [
        migrations.RunPython(drop_duplicate_outbound, migrations.RunPython.noop),
    ]
