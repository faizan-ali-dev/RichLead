"""Apollo prospect search and verified-work-email import."""

import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from leads.models import IntentSignal, Lead
from richlead_backend.caching import cache_call
from integrations.models import APIIntegration
from ai_engine.services import generate_outreach_message
from integrations.services import send_outreach_email

logger = logging.getLogger(__name__)

APOLLO_API_BASE = "https://api.apollo.io/api/v1/"
# Keep the first integration test intentionally small. Apollo's people search is
# credit-free, but revealing/enriching addresses can consume credits per person.
MAX_LEADS_PER_SEARCH = 10
DEFAULT_LEAD_COUNT = 10
BULK_ENRICHMENT_SIZE = 10
UNLOCKED_EMAIL_PLACEHOLDER = "email_not_unlocked@domain.com"


class ApolloAPIError(Exception):
    """A safe, user-facing Apollo API error without leaking credentials."""


def _coerce_count(raw):
    try:
        count = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LEAD_COUNT
    if count <= 0:
        return DEFAULT_LEAD_COUNT
    return min(count, MAX_LEADS_PER_SEARCH)


def _apollo_post(api_key, endpoint, *, params=None, json=None):
    try:
        response = requests.post(
            urljoin(APOLLO_API_BASE, endpoint),
            params=params,
            json=json,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            },
            timeout=(5, 30),
        )
    except requests.Timeout as exc:
        raise ApolloAPIError("Apollo timed out. Try again in a moment.") from exc
    except requests.RequestException as exc:
        raise ApolloAPIError("Could not connect to Apollo. Check the API connection and try again.") from exc

    if not response.ok:
        # Do not include raw response text; provider errors can contain account details.
        if response.status_code == 401:
            message = "Apollo rejected this API key. Check the key in Settings → API Integrations."
        elif response.status_code == 403:
            message = "This Apollo plan or API key does not have access to this endpoint."
        elif response.status_code == 429:
            message = "Apollo rate limit reached. Wait a little and try again."
        else:
            message = f"Apollo request failed (HTTP {response.status_code})."
        logger.warning("Apollo %s request failed with HTTP %s", endpoint, response.status_code)
        raise ApolloAPIError(message)

    try:
        return response.json()
    except ValueError as exc:
        raise ApolloAPIError("Apollo returned an unreadable response. Please try again.") from exc


def _search_apollo_people(api_key, search_params, count):
    titles = search_params.get("job_titles") or "CEO"
    if isinstance(titles, str):
        titles = [title.strip() for title in titles.split(",") if title.strip()]
    else:
        titles = [str(title).strip() for title in titles if str(title).strip()]

    query = [
        ("contact_email_status[]", "verified"),
        ("page", "1"),
        ("per_page", str(count)),
    ]
    query.extend(("person_titles[]", title) for title in titles)

    location = search_params.get("location")
    if location:
        locations = location if isinstance(location, list) else [part.strip() for part in str(location).split(",") if part.strip()]
        query.extend(("person_locations[]", item) for item in locations)

    keywords = search_params.get("keywords")
    if keywords:
        query.append(("q_keywords", str(keywords).strip()))

    payload = _apollo_post(api_key, "mixed_people/api_search", params=query, json={})
    people = payload.get("people", [])
    if not isinstance(people, list):
        raise ApolloAPIError("Apollo returned an unexpected people-search response.")
    return people, payload.get("total_entries", len(people))


def _search_apollo_companies(api_key, search_params, count, user_id):
    """Search organizations without inventing contact records or email addresses."""
    query = [("page", "1"), ("per_page", str(count))]
    location = search_params.get("location")
    if location:
        locations = location if isinstance(location, list) else [part.strip() for part in str(location).split(",") if part.strip()]
        query.extend(("organization_locations[]", item) for item in locations)

    keywords = search_params.get("keywords")
    if keywords:
        query.extend(("q_organization_keyword_tags[]", item.strip()) for item in str(keywords).split(",") if item.strip())

    name = search_params.get("company_name")
    if name:
        query.append(("q_organization_name", str(name).strip()))

    # This is the enabled legacy organization-search scope shown in the user's
    # Apollo API-key picker; mixed_companies/search is blocked for this key.
    payload = cache_call(
        "apollo-company-preview",
        parts={
            "user_id": user_id,
            "api_key": api_key,
            "search_params": search_params,
            "count": count,
        },
        timeout=settings.CACHE_APOLLO_PREVIEW_TTL,
        producer=lambda: _apollo_post(api_key, "organizations/search", params=query, json={}),
    )
    organizations = payload.get("organizations", [])
    if not isinstance(organizations, list):
        raise ApolloAPIError("Apollo returned an unexpected company-search response.")

    return organizations, payload.get("pagination", {}).get("total_entries", len(organizations))


def _search_apollo_contacts(api_key, search_params, count):
    """Search contacts already saved in the user's Apollo workspace."""
    keywords = search_params.get("keywords") or search_params.get("job_titles") or ""
    payload = _apollo_post(
        api_key,
        "contacts/search",
        json={"q_keywords": str(keywords).strip(), "page": 1, "per_page": count},
    )
    contacts = payload.get("contacts", [])
    if not isinstance(contacts, list):
        raise ApolloAPIError("Apollo returned an unexpected saved-contacts response.")
    return contacts, payload.get("pagination", {}).get("total_entries", len(contacts))


def _verified_apollo_contacts(api_key, search_params, count):
    contacts, total_entries = _search_apollo_contacts(api_key, search_params, count)
    verified = []
    for contact in contacts:
        if not isinstance(contact, dict) or (contact.get("email_status") or "").lower() != "verified":
            continue
        email = (contact.get("email") or "").strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            continue
        item = dict(contact)
        item["email"] = email
        organization = item.get("organization") or {}
        item["organization"] = organization if isinstance(organization, dict) else {"name": item.get("organization_name") or ""}
        item.setdefault("name", " ".join(filter(None, (item.get("first_name"), item.get("last_name")))))
        item.setdefault("title", "")
        if "phone" in (search_params.get("fields") or []) and not (item.get("phone_number") or item.get("sanitized_phone") or item.get("phone_numbers")):
            continue
        verified.append(item)
    return verified, total_entries


def _company_has_field(company, field):
    if field == "phone":
        primary_phone = company.get("primary_phone") or {}
        return bool(company.get("phone") or (primary_phone.get("number") if isinstance(primary_phone, dict) else primary_phone))
    if field == "company_website":
        return bool(company.get("website_url") or company.get("primary_domain"))
    if field == "linkedin":
        return bool(company.get("linkedin_url"))
    if field == "funding_data":
        return bool(company.get("latest_funding_round") or company.get("latest_funding_amount") or company.get("total_funding"))
    return False


def _fetch_apollo_companies(api_key, search_params, count, user_id):
    try:
        organizations, total_entries = _search_apollo_companies(api_key, search_params, count, user_id)
    except ApolloAPIError as exc:
        return {"success": False, "error": str(exc)}

    required_fields = search_params.get("fields") or []
    required_fields = [field for field in required_fields if field in {"phone", "company_website", "linkedin", "funding_data"}]
    companies = []
    for organization in organizations:
        if not isinstance(organization, dict):
            continue
        if required_fields and not all(_company_has_field(organization, field) for field in required_fields):
            continue
        companies.append({
            "id": organization.get("id"),
            "name": organization.get("name") or "Unnamed company",
            "website": organization.get("website_url") or organization.get("primary_domain") or "",
            "phone": organization.get("phone") or ((organization.get("primary_phone") or {}).get("number") if isinstance(organization.get("primary_phone"), dict) else organization.get("primary_phone") or ""),
            "linkedin": organization.get("linkedin_url") or "",
            "location": organization.get("primary_location") or organization.get("organization_location") or "",
            "industry": organization.get("industry") or "",
            "employee_count": organization.get("estimated_num_employees"),
            "funding": organization.get("total_funding") or organization.get("latest_funding_amount") or "",
        })

    return {
        "success": True,
        "lead_type": "companies",
        "companies": companies,
        "fetched_count": len(companies),
        "search_matches": total_entries,
        "returned_count": len(organizations),
        "filtered_count": max(0, len(organizations) - len(companies)),
        "required_fields": required_fields,
        "saved_to_leads": False,
        "max_leads_per_search": MAX_LEADS_PER_SEARCH,
    }


def _enrich_verified_emails(api_key, people, *, reveal_phone_number=False):
    """Reveal work email addresses in batches and keep only Apollo-verified ones."""
    candidates = [person for person in people if person.get("id") and person.get("has_email") is True]
    verified_people = []

    for start in range(0, len(candidates), BULK_ENRICHMENT_SIZE):
        batch = candidates[start:start + BULK_ENRICHMENT_SIZE]
        result = _apollo_post(
            api_key,
            "people/bulk_match",
            params={"reveal_personal_emails": "false", "reveal_phone_number": "true" if reveal_phone_number else "false"},
            json={"details": [{"id": person["id"]} for person in batch]},
        )
        matches = result.get("matches", [])
        if not isinstance(matches, list):
            raise ApolloAPIError("Apollo returned an unexpected email-enrichment response.")

        for person in matches:
            if not isinstance(person, dict) or (person.get("email_status") or "").lower() != "verified":
                continue
            email = (person.get("email") or "").strip().lower()
            if not email or email == UNLOCKED_EMAIL_PLACEHOLDER:
                continue
            try:
                validate_email(email)
            except ValidationError:
                continue
            verified_people.append(person)

    return verified_people


def _apollo_location(person, organization):
    location = person.get("city") or person.get("person_city")
    region = person.get("state") or person.get("person_state")
    country = person.get("country") or person.get("person_country")
    parts = [part for part in (location, region, country) if part]
    if parts:
        return ", ".join(parts)
    org_location = organization.get("primary_location") or organization.get("organization_location") or ""
    if isinstance(org_location, dict):
        return ", ".join(str(org_location.get(key)) for key in ("city", "state", "country") if org_location.get(key))
    return str(org_location)


def _apollo_phone(person):
    phone = person.get("phone_number") or person.get("sanitized_phone") or person.get("phone") or ""
    if isinstance(phone, dict):
        return phone.get("number") or phone.get("sanitized_number") or ""
    if isinstance(phone, list):
        phone = phone[0] if phone else ""
        return (phone.get("number") or phone.get("sanitized_number") or "") if isinstance(phone, dict) else str(phone)
    return str(phone)


def _get_apollo_api_key(user):
    try:
        integration = APIIntegration.objects.get(user=user, provider="apollo", is_active=True)
        return integration.get_api_key()
    except APIIntegration.DoesNotExist:
        return None
    except Exception:
        logger.exception("Unable to decrypt this user's Apollo API key")
        raise ApolloAPIError("The saved Apollo API key could not be read. Please reconnect Apollo.")


def fetch_apollo_leads(user, search_params):
    """Search Apollo, enrich addresses, and import only email_status=verified."""
    search_params = search_params or {}
    count = _coerce_count(search_params.get("count", DEFAULT_LEAD_COUNT))

    try:
        api_key = _get_apollo_api_key(user)
        if not api_key:
            return {
                "success": False,
                "error": "Apollo is not connected. Add your API key under Settings → API Integrations.",
            }

        if search_params.get("lead_type") == "companies":
            return _fetch_apollo_companies(api_key, search_params, count, user.pk)

        if search_params.get("lead_type") == "contacts":
            verified_people, total_entries = _verified_apollo_contacts(api_key, search_params, count)
        else:
            people, total_entries = _search_apollo_people(api_key, search_params, count)
            required_fields = set(search_params.get("fields") or [])
            verified_people = _enrich_verified_emails(api_key, people, reveal_phone_number="phone" in required_fields)
    except ApolloAPIError as exc:
        return {"success": False, "error": str(exc)}

    required_fields = set(search_params.get("fields") or [])
    if "linkedin" in required_fields:
        verified_people = [
            person for person in verified_people
            if person.get("linkedin_url") or (person.get("organization") or {}).get("linkedin_url")
        ]
    if "company_website" in required_fields:
        verified_people = [
            person for person in verified_people
            if (person.get("organization") or {}).get("website_url")
            or (person.get("organization") or {}).get("primary_domain")
        ]
    if "phone" in required_fields:
        verified_people = [person for person in verified_people if person.get("phone_number") or person.get("sanitized_phone") or person.get("phone") or person.get("phone_numbers")]

    keywords = search_params.get("keywords") or "Apollo"
    created_leads = []
    skipped_duplicates = 0

    for person in verified_people:
        organization = person.get("organization") or {}
        name = (person.get("name") or " ".join(filter(None, [person.get("first_name"), person.get("last_name")]))).strip()
        email = person["email"].strip().lower()
        if not name:
            name = email.split("@", 1)[0]

        try:
            with transaction.atomic():
                lead = Lead.objects.create(
                    user=user,
                    name=name,
                    email=email,
                    company=organization.get("name") or "Unknown company",
                    title=person.get("title") or "",
                    niche=str(keywords)[:100],
                    phone=_apollo_phone(person),
                    website=organization.get("website_url") or organization.get("primary_domain") or "",
                    linkedin_url=person.get("linkedin_url") or organization.get("linkedin_url") or "",
                    industry=organization.get("industry") or "",
                    location=_apollo_location(person, organization),
                    employee_count=organization.get("estimated_num_employees") or None,
                    funding_amount=str(organization.get("latest_funding_amount") or organization.get("total_funding") or ""),
                    funding_round=organization.get("latest_funding_round") or "",
                    funding_data={
                        key: organization[key]
                        for key in ("latest_funding_amount", "latest_funding_round", "latest_funding_date", "total_funding")
                        if organization.get(key) is not None
                    },
                    source="apollo",
                    source_id=str(person.get("id") or ""),
                    icp_score=0,
                    status="pending",
                )
        except IntegrityError:
            skipped_duplicates += 1
            continue

        IntentSignal.objects.create(lead=lead, signal=f"Verified Apollo email for {keywords}")
        created_leads.append(lead)

        ai_result = generate_outreach_message(lead.id, user)
        if not ai_result.get("success"):
            logger.warning("AI generation failed for lead %s: %s", lead.id, ai_result.get("error"))
            continue

        if user.autopilot_active:
            send_result = send_outreach_email(lead.id, user, ai_result["message"])
            if not send_result.get("success"):
                logger.info("Autopilot skipped lead %s: %s", lead.id, send_result.get("error"))

    return {
        "success": True,
        "lead_type": search_params.get("lead_type", "people"),
        "fetched_count": len(created_leads),
        "skipped_duplicates": skipped_duplicates,
        "verified_only": True,
        "verified_candidates": len(verified_people),
        "search_matches": total_entries,
        "max_leads_per_search": MAX_LEADS_PER_SEARCH,
    }
