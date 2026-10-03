from integrations.hunter_service import fetch_hunter_leads, validate_hunter_api_key
from integrations.models import APIIntegration
from leads.models import Lead


def test_hunter_api_key_validation_uses_free_account_endpoint(monkeypatch):
    calls = []

    def fake_request(api_key, endpoint, **kwargs):
        calls.append((api_key, endpoint, kwargs))
        return {"data": {"email": "owner@example.test", "plan_name": "Free"}}

    monkeypatch.setattr("integrations.hunter_service._hunter_request", fake_request)
    account = validate_hunter_api_key("hunter-test-key")

    assert account["plan_name"] == "Free"
    assert calls[0][1] == "account"


def test_hunter_people_imports_only_valid_personal_work_emails(user_a, monkeypatch):
    APIIntegration.objects.create(user=user_a, provider="hunter", encrypted_api_key="encrypted-test-key")
    monkeypatch.setattr(APIIntegration, "get_api_key", lambda _self: "hunter-test-key")
    monkeypatch.setattr(
        "integrations.hunter_service._hunter_request",
        lambda _api_key, endpoint, **kwargs: {
            "data": {
                "domain": "example.test",
                "organization": "Example Co",
                "emails": [
                    {
                        "value": "valid@example.test",
                        "first_name": "Verified",
                        "last_name": "Person",
                        "position": "CEO",
                        "phone_number": "+1 555 0100",
                        "linkedin": "https://linkedin.com/in/verified",
                        "verification": {"status": "valid"},
                    },
                    {
                        "value": "unknown@example.test",
                        "verification": {"status": "unknown"},
                    },
                ],
            },
            "meta": {"results": 2},
        },
    )
    monkeypatch.setattr(
        "integrations.hunter_service.generate_outreach_message",
        lambda *_args: {"success": True, "message": "Draft"},
    )

    result = fetch_hunter_leads(
        user_a,
        {"lead_type": "people", "company_name": "example.test", "domain": "example.test", "count": 2},
    )

    assert result["success"] is True
    assert result["verified_only"] is True
    assert result["fetched_count"] == 1
    lead = Lead.objects.get(user=user_a)
    assert lead.email == "valid@example.test"
    assert lead.company == "Example Co"
    assert lead.phone == "+1 555 0100"
    assert lead.linkedin_url == "https://linkedin.com/in/verified"
    assert lead.source == "hunter"
    assert lead.source_id == "example.test:valid@example.test"
    assert lead.email_status == "verified"


def test_hunter_company_discover_is_preview_only_and_does_not_create_leads(user_a, monkeypatch):
    APIIntegration.objects.create(user=user_a, provider="hunter", encrypted_api_key="encrypted-test-key")
    monkeypatch.setattr(APIIntegration, "get_api_key", lambda _self: "hunter-test-key")
    calls = []

    def fake_request(_api_key, endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return {
            "data": [{"domain": "example.test", "organization": "Example Co", "emails_count": {"total": 12}}],
            "meta": {"results": 1},
        }

    monkeypatch.setattr("integrations.hunter_service._hunter_request", fake_request)
    result = fetch_hunter_leads(user_a, {"lead_type": "companies", "keywords": "SaaS", "location": "US"})

    assert result["success"] is True
    assert result["preview_only"] is True
    assert result["companies"][0]["emails_count"] == 12
    assert calls[0][0] == "discover"
    assert Lead.objects.filter(user=user_a).count() == 0


def test_hunter_people_search_requires_a_company_or_domain(user_a, monkeypatch):
    APIIntegration.objects.create(user=user_a, provider="hunter", encrypted_api_key="encrypted-test-key")
    monkeypatch.setattr(APIIntegration, "get_api_key", lambda _self: "hunter-test-key")

    result = fetch_hunter_leads(user_a, {"lead_type": "people"})

    assert result["success"] is False
    assert "company name or domain" in result["error"]
