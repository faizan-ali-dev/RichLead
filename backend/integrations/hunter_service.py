"""Hunter API integration for company discovery and verified contact import."""

import logging
from urllib.parse import urlparse

import requests
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from ai_engine.services import generate_outreach_message
from integrations.models import APIIntegration
from integrations.services import send_outreach_email
from leads.models import IntentSignal, Lead

logger = logging.getLogger(__name__)
HUNTER_API_BASE = "https://api.hunter.io/v2/"
MAX_HUNTER_RESULTS = 10


class HunterAPIError(Exception):
    """Safe user-facing Hunter error; never contains an API key or raw response."""


def _hunter_request(api_key, endpoint, *, method="GET", params=None, json=None):
    try:
        response = requests.request(
            method,
            f"{HUNTER_API_BASE}{endpoint.lstrip('/')}",
            params=params,
            json=json,
            headers={"X-API-KEY": api_key, "Accept": "application/json"},
            timeout=(5, 30),
        )
    except requests.Timeout as exc:
        raise HunterAPIError("Hunter timed out. Please try again shortly.") from exc
    except requests.RequestException as exc:
        raise HunterAPIError("Could not connect to Hunter. Please try again.") from exc

    if not response.ok:
        if response.status_code == 401:
            message = "Hunter rejected this API key. Check it under Settings → API Integrations."
        elif response.status_code == 403:
            message = "This Hunter plan does not have access to that endpoint."
        elif response.status_code == 429:
            message = "Hunter usage limit reached. Check your remaining credits or request quota."
        elif response.status_code == 451:
            message = "Hunter cannot process this contact due to a privacy request."
        elif response.status_code == 400:
            message = "Hunter could not use these search filters. Check the company, location, and search terms."
        else:
            message = f"Hunter request failed (HTTP {response.status_code})."
        logger.warning("Hunter %s request failed with HTTP %s", endpoint, response.status_code)
        raise HunterAPIError(message)

    try:
        payload = response.json()
    except ValueError as exc:
        raise HunterAPIError("Hunter returned an unreadable response.") from exc
    if not isinstance(payload, dict) or payload.get("errors"):
        raise HunterAPIError("Hunter could not complete this request. Check the API key and filters.")
    return payload


def validate_hunter_api_key(api_key):
    """Check a key using Hunter's free account endpoint (no lead credits consumed)."""
    if not api_key or not api_key.strip():
        raise HunterAPIError("Enter a Hunter API key.")
    payload = _hunter_request(api_key.strip(), "account")
    account = payload.get("data")
    if not isinstance(account, dict):
        raise HunterAPIError("Hunter did not return account details for this API key.")
    return account


def _api_key_for(user):
    try:
        integration = APIIntegration.objects.get(user=user, provider="hunter", is_active=True)
        return integration.get_api_key()
    except APIIntegration.DoesNotExist as exc:
        raise HunterAPIError("Hunter is not connected. Add your API key under Settings → API Integrations.") from exc
    except Exception as exc:
        logger.exception("Unable to decrypt the saved Hunter API key")
        raise HunterAPIError("The saved Hunter key could not be read. Please reconnect Hunter.") from exc


def _count(raw):
    try:
        return min(max(int(raw), 1), MAX_HUNTER_RESULTS)
    except (TypeError, ValueError):
        return MAX_HUNTER_RESULTS


def _normalize_domain(raw):
    value = (raw or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"//{value}")
    domain = (parsed.netloc or parsed.path).split("/")[0].lower().removeprefix("www.")
    return domain if "." in domain else ""


def _discover_companies(api_key, search_params):
    company_name = (search_params.get("company_name") or "").strip()
    keywords = (search_params.get("keywords") or "").strip()
    location = (search_params.get("location") or "").strip()
    if company_name:
        body = {"organization": {"name": [company_name]}}
    else:
        query_parts = [part for part in (keywords, location) if part]
        if not query_parts:
            raise HunterAPIError("Enter a company name, industry/keyword, or location to search companies.")
        body = {"query": "Companies " + " in ".join(query_parts)}

    payload = _hunter_request(api_key, "discover", method="POST", json=body)
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise HunterAPIError("Hunter returned an unexpected company-search response.")
    companies = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        domain = row.get("domain") or ""
        counts = row.get("emails_count") or {}
        companies.append({
            "id": domain or row.get("organization"),
            "name": row.get("organization") or domain or "Unnamed company",
            "website": domain,
            "phone": "",
            "linkedin": "",
            "location": "",
            "industry": "",
            "employee_count": None,
            "funding": "",
            "emails_count": counts.get("total", 0),
            "source": "hunter",
        })
    meta = payload.get("meta") or {}
    return {
        "success": True,
        "lead_type": "companies",
        "companies": companies[:MAX_HUNTER_RESULTS],
        "fetched_count": min(len(companies), MAX_HUNTER_RESULTS),
        "search_matches": meta.get("results", len(companies)),
        "returned_count": len(companies),
        "filtered_count": 0,
        "saved_to_leads": False,
        "preview_only": True,
        "credit_note": "Hunter Discover company search is free; finding contact emails uses credits.",
        "max_leads_per_search": MAX_HUNTER_RESULTS,
    }


def _domain_search(api_key, search_params, count):
    domain = _normalize_domain(search_params.get("domain"))
    company = (search_params.get("company_name") or "").strip()
    if not domain and not company:
        raise HunterAPIError("For Hunter people search, enter a company name or domain.")

    params = {"limit": count, "type": "personal", "verification_status": "valid"}
    if domain:
        params["domain"] = domain
    else:
        params["company"] = company
    titles = search_params.get("job_titles") or ""
    if isinstance(titles, list):
        titles = ",".join(str(value).strip() for value in titles if str(value).strip())
    if titles:
        params["job_titles"] = str(titles).strip()

    fields = set(search_params.get("fields") or [])
    required = ["full_name", "position"]
    if "phone" in fields:
        required.append("phone_number")
    params["required_field"] = ",".join(required)

    location = (search_params.get("location") or "").strip()
    body = None
    method = "GET"
    if location:
        if len(location) != 2 or not location.isalpha():
            raise HunterAPIError("Hunter location filter needs a 2-letter country code, for example US or GB.")
        method = "POST"
        body = {"location": {"include": [{"country": location.upper()}]}}

    payload = _hunter_request(api_key, "domain-search", method=method, params=params, json=body)
    result = payload.get("data") or {}
    emails = result.get("emails") or []
    if not isinstance(emails, list):
        raise HunterAPIError("Hunter returned an unexpected contact-search response.")
    return result, emails, payload.get("meta") or {}


def _passes_requested_fields(email, organization, fields):
    if "phone" in fields and not email.get("phone_number"):
        return False
    if "linkedin" in fields and not email.get("linkedin"):
        return False
    if "company_website" in fields and not (organization.get("domain") or organization.get("website")):
        return False
    return True


def fetch_hunter_leads(user, search_params):
    """Search Hunter and import only Hunter-valid personal work emails."""
    search_params = search_params or {}
    try:
        api_key = _api_key_for(user)
        if search_params.get("lead_type") == "companies":
            return _discover_companies(api_key, search_params)
        if search_params.get("lead_type") == "contacts":
            raise HunterAPIError("Hunter does not provide an import-my-saved-contacts source.")

        count = _count(search_params.get("count"))
        organization, email_rows, meta = _domain_search(api_key, search_params, count)
    except HunterAPIError as exc:
        return {"success": False, "error": str(exc)}

    fields = set(search_params.get("fields") or [])
    keyword = str(search_params.get("keywords") or "Hunter")[:100]
    created = []
    skipped_duplicates = 0
    verified_candidates = 0
    for item in email_rows:
        if not isinstance(item, dict):
            continue
        email = (item.get("value") or "").strip().lower()
        if (item.get("verification") or {}).get("status", "").lower() != "valid":
            continue
        try:
            validate_email(email)
        except ValidationError:
            continue
        if not _passes_requested_fields(item, organization, fields):
            continue
        verified_candidates += 1
        name = " ".join(filter(None, (item.get("first_name"), item.get("last_name")))).strip() or email.split("@", 1)[0]
        domain = organization.get("domain") or email.split("@", 1)[1]
        company = organization.get("organization") or search_params.get("company_name") or domain
        try:
            with transaction.atomic():
                lead = Lead.objects.create(
                    user=user,
                    name=name,
                    company=company,
                    title=item.get("position") or "",
                    niche=keyword,
                    email=email,
                    phone=item.get("phone_number") or "",
                    website=domain,
                    linkedin_url=item.get("linkedin") or "",
                    location=item.get("country") or item.get("city") or "",
                    source="hunter",
                    source_id=f"{domain}:{email}",
                    icp_score=0,
                    status="pending",
                )
        except IntegrityError:
            skipped_duplicates += 1
            continue

        IntentSignal.objects.create(lead=lead, signal=f"Hunter-verified email for {company}")
        created.append(lead)
        ai_result = generate_outreach_message(lead.id, user)
        if not ai_result.get("success"):
            logger.warning("AI generation failed for Hunter lead %s: %s", lead.id, ai_result.get("error"))
            continue
        if user.autopilot_active:
            send_result = send_outreach_email(lead.id, user, ai_result["message"])
            if not send_result.get("success"):
                logger.info("Autopilot skipped Hunter lead %s: %s", lead.id, send_result.get("error"))

    return {
        "success": True,
        "lead_type": "people",
        "fetched_count": len(created),
        "skipped_duplicates": skipped_duplicates,
        "verified_only": True,
        "verified_candidates": verified_candidates,
        "search_matches": meta.get("results", len(email_rows)),
        "max_leads_per_search": MAX_HUNTER_RESULTS,
        "credit_note": "Hunter charges credits when matching personal emails are returned; only valid work emails are imported.",
    }
