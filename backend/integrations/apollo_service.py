import logging
import random

from django.db import IntegrityError, transaction

from leads.models import Lead, IntentSignal
from integrations.models import APIIntegration
from ai_engine.services import generate_outreach_message
from integrations.services import send_outreach_email

logger = logging.getLogger(__name__)

# Each lead costs one AI completion (and, under autopilot, one send). Without a
# ceiling a single request could trigger thousands of paid API calls.
MAX_LEADS_PER_SEARCH = 100
DEFAULT_LEAD_COUNT = 10


def _coerce_count(raw):
    try:
        count = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LEAD_COUNT
    if count <= 0:
        return DEFAULT_LEAD_COUNT
    return min(count, MAX_LEADS_PER_SEARCH)


def _mock_lead_batch(count, job_titles, keywords):
    """Sandbox data stand-in until a real Apollo key is wired up.

    Seam kept separate so tests can substitute deterministic batches.
    """
    return [
        {
            "name": f"Lead {random.randint(1000, 9999)}",
            "email": f"lead{random.randint(100000, 999999)}@example.com",
            "company": f"{keywords} Company {i}",
            "title": job_titles,
            "niche": keywords,
        }
        for i in range(count)
    ]


def fetch_apollo_leads(user, search_params):
    """
    Fetches leads from Apollo based on search parameters.
    Then orchestrates AI generation and autopilot sending.
    """
    search_params = search_params or {}

    # Apollo key is read but not yet used: sourcing is still sandbox-only.
    api_key = None
    try:
        integration = APIIntegration.objects.get(user=user, provider='apollo', is_active=True)
        api_key = integration.get_api_key()
    except APIIntegration.DoesNotExist:
        pass

    job_titles = search_params.get('job_titles') or 'CEO'
    keywords = search_params.get('keywords') or 'Tech'
    count = _coerce_count(search_params.get('count', DEFAULT_LEAD_COUNT))

    batch = _mock_lead_batch(count, job_titles, keywords)

    created_leads = []
    skipped = 0

    for data in batch:
        try:
            with transaction.atomic():
                lead = Lead.objects.create(
                    user=user,
                    name=data['name'],
                    email=data['email'],
                    company=data['company'],
                    title=data.get('title', ''),
                    niche=data['niche'],
                    icp_score=random.randint(70, 99),
                    status='pending',
                )
        except IntegrityError:
            # Already prospected by this user; not an error worth failing the batch over.
            skipped += 1
            continue

        IntentSignal.objects.create(lead=lead, signal=f"Searching for {keywords} services")
        created_leads.append(lead)

        ai_result = generate_outreach_message(lead.id, user)
        if not ai_result.get('success'):
            logger.warning("AI generation failed for lead %s: %s", lead.id, ai_result.get('error'))
            continue

        if user.autopilot_active:
            # send_outreach_email owns the suppression and blacklist checks.
            send_result = send_outreach_email(lead.id, user, ai_result['message'])
            if not send_result.get('success'):
                logger.info("Autopilot skipped lead %s: %s", lead.id, send_result.get('error'))

    return {
        "success": True,
        "fetched_count": len(created_leads),
        "skipped_duplicates": skipped,
        "sandbox": api_key is None,
    }
