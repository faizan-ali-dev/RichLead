"""Re-encrypt stored credentials from one Fernet key to the current one.

Needed when FERNET_KEY changes -- notably when migrating off the hardcoded key that
used to ship in integrations/models.py. Without this, every stored credential becomes
undecryptable and users silently lose their connected mailboxes.

    python manage.py rotate_encryption_key --old-key '<previous key>'

Credentials that were encrypted under a publicly known key should still be treated as
compromised: rotate them at the provider and reconnect. This command only preserves
continuity so the app keeps working while that happens.
"""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from integrations.models import APIIntegration, EmailAccount

# Fields holding ciphertext, per model.
ENCRYPTED_FIELDS = {
    APIIntegration: ['encrypted_api_key'],
    EmailAccount: [
        'encrypted_password',
        'encrypted_imap_password',
        'encrypted_access_token',
        'encrypted_refresh_token',
    ],
}


class Command(BaseCommand):
    help = "Re-encrypt stored credentials from --old-key to the current FERNET_KEY."

    def add_arguments(self, parser):
        parser.add_argument('--old-key', required=True, help="The Fernet key the data is currently encrypted with.")
        parser.add_argument('--dry-run', action='store_true', help="Report what would change without writing.")

    def handle(self, *args, **options):
        try:
            old_cipher = Fernet(options['old_key'].encode())
        except Exception as exc:
            raise CommandError(f"--old-key is not a valid Fernet key: {exc}")

        new_cipher = Fernet(
            settings.FERNET_KEY if isinstance(settings.FERNET_KEY, bytes) else settings.FERNET_KEY.encode()
        )
        dry_run = options['dry_run']

        rotated = skipped = failed = 0

        for model, fields in ENCRYPTED_FIELDS.items():
            for obj in model.objects.all():
                changed = False
                for field in fields:
                    blob = getattr(obj, field, None)
                    if not blob:
                        continue

                    # Already on the new key? Leave it alone -- makes this idempotent.
                    try:
                        new_cipher.decrypt(blob.encode())
                        skipped += 1
                        continue
                    except InvalidToken:
                        pass

                    try:
                        plaintext = old_cipher.decrypt(blob.encode())
                    except InvalidToken:
                        self.stderr.write(
                            self.style.WARNING(f"  {model.__name__}#{obj.pk}.{field}: not readable with --old-key")
                        )
                        failed += 1
                        continue

                    setattr(obj, field, new_cipher.encrypt(plaintext).decode())
                    changed = True
                    rotated += 1

                if changed and not dry_run:
                    obj.save(update_fields=fields)

        verb = "would rotate" if dry_run else "rotated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {rotated} value(s); {skipped} already current; {failed} unreadable"))
        if failed:
            self.stdout.write(
                self.style.WARNING("Unreadable values must be re-entered by the user through the UI.")
            )
