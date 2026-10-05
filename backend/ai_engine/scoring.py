"""ICP fit scoring.

Ranks leads by how well they match the tenant's ideal-customer profile, using the
enrichment fields the prospecting providers populate (title, industry, location,
employee_count, funding). The score (0-100) drives queue and draft ordering so the
best-fit prospects are worked first, and the per-factor breakdown is stored so a
human can see *why* a lead ranked where it did.

Scoring is deterministic and offline -- no LLM call -- so it is cheap enough to run
on every lead at import time and re-run in bulk when the ICP changes.
"""
from leads.models import Lead, ScoreBreakdown

# Each factor contributes up to `max` points; the total is normalised to 100.
# Weights reflect what actually predicts a reply: reaching the right person
# (title) and the right kind of company (industry, size) matters most.
FACTOR_WEIGHTS = {
    'title': 30,
    'industry': 25,
    'company_size': 20,
    'location': 15,
    'funding': 10,
}

# A lead with no ICP configured still needs a stable baseline so the queue has a
# sensible default order rather than everything tying at zero.
NEUTRAL_SCORE = 50


def _text_match_fraction(value, keywords):
    """1.0 for a direct hit, partial credit for a keyword substring, else 0."""
    value = (value or '').strip().lower()
    terms = [k.strip().lower() for k in (keywords or []) if k and k.strip()]
    if not value or not terms:
        return None  # nothing to score this factor on
    for term in terms:
        if term == value:
            return 1.0
    for term in terms:
        if term in value or value in term:
            return 0.6
    return 0.0


def _best_match_fraction(values, keywords):
    """Best match fraction across several candidate fields. None if none scorable."""
    fractions = [f for f in (_text_match_fraction(v, keywords) for v in values) if f is not None]
    return max(fractions) if fractions else None


def _company_size_fraction(employee_count, low, high):
    if employee_count is None or (low is None and high is None):
        return None
    if low is not None and employee_count < low:
        # Partial credit near the boundary; a 45-person company for a 50+ ICP is
        # a near miss, a 3-person company is not.
        return max(0.0, 1.0 - (low - employee_count) / max(low, 1))
    if high is not None and employee_count > high:
        return max(0.0, 1.0 - (employee_count - high) / max(high, 1))
    return 1.0


def _funding_fraction(lead, requires_funding):
    if not requires_funding:
        return None
    has_funding = bool((lead.funding_amount or '').strip() or (lead.funding_round or '').strip() or lead.funding_data)
    return 1.0 if has_funding else 0.0


def compute_icp_score(lead, profile):
    """Return (score 0-100, breakdown rows) for one lead against an ICP.

    Factors with nothing to score against (no criterion, or no enrichment data)
    are skipped and excluded from the denominator, so a sparse profile still
    produces a meaningful score from the factors that *are* known.
    """
    if profile is None or not profile.has_icp_criteria():
        return NEUTRAL_SCORE, []

    # Industry data can live in either `industry` (from enrichment) or `niche`
    # (from the search query). Score both and keep the better match rather than
    # concatenating, which would turn an exact hit into a mere substring hit.
    industry_fraction = _best_match_fraction(
        (lead.industry, lead.niche), profile.icp_industries,
    )

    fractions = {
        'title': _text_match_fraction(lead.title, profile.icp_titles),
        'industry': industry_fraction,
        'company_size': _company_size_fraction(
            lead.employee_count, profile.icp_employee_min, profile.icp_employee_max,
        ),
        'location': _text_match_fraction(lead.location, profile.icp_locations),
        'funding': _funding_fraction(lead, profile.icp_requires_funding),
    }

    scored = {k: v for k, v in fractions.items() if v is not None}
    if not scored:
        return NEUTRAL_SCORE, []

    earned = 0.0
    possible = 0.0
    breakdown = []
    for factor, fraction in scored.items():
        weight = FACTOR_WEIGHTS[factor]
        points = round(fraction * weight)
        earned += points
        possible += weight
        breakdown.append({'factor': factor, 'score': points, 'max_score': weight})

    score = round(earned / possible * 100) if possible else NEUTRAL_SCORE
    return max(0, min(100, score)), breakdown


def apply_icp_score(lead, profile, *, persist_breakdown=True):
    """Score a lead and persist the result. Returns the numeric score.

    Writes `lead.icp_score` and replaces its ScoreBreakdown rows. Safe to call
    repeatedly; it is idempotent for a given (lead, profile) state.
    """
    score, breakdown = compute_icp_score(lead, profile)

    if lead.icp_score != score:
        lead.icp_score = score
        lead.save(update_fields=['icp_score'])

    if persist_breakdown:
        lead.score_breakdowns.all().delete()
        if breakdown:
            ScoreBreakdown.objects.bulk_create([
                ScoreBreakdown(lead=lead, factor=row['factor'], score=row['score'], max_score=row['max_score'])
                for row in breakdown
            ])

    return score


def rescore_user_leads(user, profile=None, *, statuses=('pending',)):
    """Re-score a tenant's leads after the ICP changes. Returns count updated.

    Scoped to pending leads by default: re-ranking leads already contacted has no
    effect on what gets worked next and only churns the database.
    """
    from .services import get_business_profile

    profile = profile or get_business_profile(user)
    leads = Lead.objects.filter(user=user)
    if statuses:
        leads = leads.filter(status__in=statuses)

    updated = 0
    for lead in leads.iterator():
        apply_icp_score(lead, profile)
        updated += 1
    return updated
