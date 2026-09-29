from integrations.apollo_service import MAX_LEADS_PER_SEARCH, _coerce_count, fetch_apollo_leads
from integrations.models import APIIntegration
from leads.models import Lead


def test_apollo_imports_only_verified_real_email(user_a, monkeypatch):
    APIIntegration.objects.create(user=user_a, provider="apollo", encrypted_api_key="encrypted-test-key")
    monkeypatch.setattr(APIIntegration, "get_api_key", lambda _self: "apollo-test-key")

    search_result = {
        "total_entries": 3,
        "people": [
            {"id": "person-verified", "has_email": True},
            {"id": "person-unverified", "has_email": True},
            {"id": "person-no-email", "has_email": False},
        ],
    }
    enrichment_result = {
        "matches": [
            {
                "id": "person-verified",
                "name": "Verified Person",
                "email": "verified@example.test",
                "email_status": "verified",
                "title": "CEO",
                "organization": {"name": "Verified Co"},
            },
            {
                "id": "person-unverified",
                "name": "Unverified Person",
                "email": "unverified@example.test",
                "email_status": "unverified",
                "organization": {"name": "Unverified Co"},
            },
        ]
    }
    calls = []

    def fake_apollo_post(api_key, endpoint, *, params=None, json=None):
        calls.append((api_key, endpoint, params, json))
        return search_result if endpoint == "mixed_people/api_search" else enrichment_result

    monkeypatch.setattr("integrations.apollo_service._apollo_post", fake_apollo_post)
    monkeypatch.setattr(
        "integrations.apollo_service.generate_outreach_message",
        lambda *_args: {"success": True, "message": "Draft"},
    )

    result = fetch_apollo_leads(
        user_a,
        {"job_titles": "CEO, Founder", "location": "London", "keywords": "SaaS", "count": 50},
    )

    assert result["success"] is True
    assert result["verified_only"] is True
    assert result["fetched_count"] == 1
    assert result["verified_candidates"] == 1
    lead = Lead.objects.get(user=user_a)
    assert lead.email == "verified@example.test"
    assert lead.name == "Verified Person"
    assert lead.company == "Verified Co"

    _, endpoint, search_params, _ = calls[0]
    assert endpoint == "mixed_people/api_search"
    assert ("contact_email_status[]", "verified") in search_params
    assert ("person_titles[]", "CEO") in search_params
    assert ("person_titles[]", "Founder") in search_params
    assert calls[1][1] == "people/bulk_match"
    assert calls[1][3] == {"details": [{"id": "person-verified"}, {"id": "person-unverified"}]}


def test_apollo_import_rejects_unlocked_placeholder(user_a, monkeypatch):
    APIIntegration.objects.create(user=user_a, provider="apollo", encrypted_api_key="encrypted-test-key")
    monkeypatch.setattr(APIIntegration, "get_api_key", lambda _self: "apollo-test-key")
    monkeypatch.setattr(
        "integrations.apollo_service._apollo_post",
        lambda _api_key, endpoint, **_kwargs: (
            {"people": [{"id": "person-1", "has_email": True}], "total_entries": 1}
            if endpoint == "mixed_people/api_search"
            else {"matches": [{"id": "person-1", "email": "email_not_unlocked@domain.com", "email_status": "verified"}]}
        ),
    )

    result = fetch_apollo_leads(user_a, {"count": 1})

    assert result["success"] is True
    assert result["fetched_count"] == 0
    assert Lead.objects.filter(user=user_a).count() == 0


def test_search_count_is_capped_for_credit_control():
    assert _coerce_count("100") == MAX_LEADS_PER_SEARCH == 10
    assert _coerce_count("not-a-number") == 10
