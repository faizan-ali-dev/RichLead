from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.db.models.functions import Trim
from django.utils import timezone

from ai_engine.models import BusinessProfile
from async_jobs.models import BackgroundJob
from integrations.models import APIIntegration, EmailAccount


LLM_JOB_TYPES = ('generate_draft', 'draft_queue', 'classify_replies')
ADOPTION_JOB_TYPES = (*LLM_JOB_TYPES, 'apollo_search', 'hunter_search', 'inbox_sync')
LLM_PROVIDER_LABELS = {'openai': 'OpenAI', 'anthropic': 'Anthropic', 'groq': 'Groq'}
PROVIDER_LABELS = {**LLM_PROVIDER_LABELS, 'apollo': 'Apollo', 'hunter': 'Hunter'}
User = get_user_model()


def _job_usage(total=0, succeeded=0, failed=0, last_run=None):
    return {
        'runs_30d': total,
        'succeeded_30d': succeeded,
        'failed_30d': failed,
        'last_run_at': last_run,
    }


def user_adoption(user_ids):
    """Get a small, privacy-safe setup summary and usage counts per user."""
    user_ids = list(user_ids)
    if not user_ids:
        return {}

    adoption = {
        user_id: {
            'business_profile': {'status': 'not_started', 'icp_configured': False},
            'llm': {
                'status': 'not_configured', 'providers': [], 'configured_providers': [],
                'primary_provider': '', 'last_validated_at': None,
            },
            'apollo': {'status': 'not_configured', **_job_usage()},
            'hunter': {'status': 'not_configured', **_job_usage()},
            'ai_activity': _job_usage(),
            'mailbox': {'connected_count': 0, 'sync': _job_usage()},
        }
        for user_id in user_ids
    }

    profile_fields = (
        'user_id', 'company_name', 'website', 'industry', 'what_you_do', 'problem_you_solve',
        'ideal_customer', 'differentiator', 'proof_points', 'case_study', 'never_claim',
        'sender_name', 'sender_title', 'icp_titles', 'icp_industries', 'icp_locations',
        'icp_employee_min', 'icp_employee_max', 'icp_requires_funding',
    )
    for profile in BusinessProfile.objects.filter(user_id__in=user_ids).values(*profile_fields):
        text_fields = (
            'company_name', 'website', 'industry', 'what_you_do', 'problem_you_solve',
            'ideal_customer', 'differentiator', 'proof_points', 'case_study', 'never_claim',
            'sender_name', 'sender_title',
        )
        has_details = any((profile[field] or '').strip() for field in text_fields)
        has_icp = bool(
            profile['icp_titles'] or profile['icp_industries'] or profile['icp_locations']
            or profile['icp_employee_min'] is not None or profile['icp_employee_max'] is not None
            or profile['icp_requires_funding']
        )
        complete = bool((profile['what_you_do'] or '').strip() and (profile['problem_you_solve'] or '').strip())
        adoption[profile['user_id']]['business_profile'] = {
            'status': 'complete' if complete else 'started' if has_details or has_icp else 'not_started',
            'icp_configured': has_icp,
        }

    for integration in APIIntegration.objects.filter(
        user_id__in=user_ids,
        provider__in=PROVIDER_LABELS,
    ).exclude(encrypted_api_key='').values(
        'user_id', 'provider', 'is_active', 'is_primary', 'last_validated_at',
    ):
        item = adoption[integration['user_id']]
        provider = integration['provider']
        label = PROVIDER_LABELS[provider]
        if provider in LLM_PROVIDER_LABELS:
            llm = item['llm']
            llm['configured_providers'].append(label)
            if integration['is_active']:
                llm['providers'].append(label)
            if integration['is_active'] and integration['is_primary']:
                llm['primary_provider'] = label
            if integration['last_validated_at'] and (
                llm['last_validated_at'] is None
                or integration['last_validated_at'] > llm['last_validated_at']
            ):
                llm['last_validated_at'] = integration['last_validated_at']
        else:
            item[provider]['status'] = 'connected' if integration['is_active'] else 'paused'

    for item in adoption.values():
        llm = item['llm']
        if llm['providers']:
            llm['status'] = 'connected'
        elif llm['configured_providers']:
            llm['status'] = 'paused'

    recent_jobs = BackgroundJob.objects.filter(
        user_id__in=user_ids,
        job_type__in=ADOPTION_JOB_TYPES,
        created_at__gte=timezone.now() - timedelta(days=30),
    ).values('user_id', 'job_type').annotate(
        total=Count('pk'),
        succeeded=Count('pk', filter=Q(status='succeeded')),
        failed=Count('pk', filter=Q(status='failed')),
        last_run=Max('created_at'),
    )
    for row in recent_jobs:
        item = adoption[row['user_id']]
        usage = _job_usage(row['total'], row['succeeded'], row['failed'], row['last_run'])
        if row['job_type'] == 'apollo_search':
            item['apollo'].update(usage)
        elif row['job_type'] == 'hunter_search':
            item['hunter'].update(usage)
        elif row['job_type'] == 'inbox_sync':
            item['mailbox']['sync'] = usage
        elif row['job_type'] in LLM_JOB_TYPES:
            ai = item['ai_activity']
            ai['runs_30d'] += usage['runs_30d']
            ai['succeeded_30d'] += usage['succeeded_30d']
            ai['failed_30d'] += usage['failed_30d']
            if usage['last_run_at'] and (ai['last_run_at'] is None or usage['last_run_at'] > ai['last_run_at']):
                ai['last_run_at'] = usage['last_run_at']

    for row in EmailAccount.objects.filter(user_id__in=user_ids, is_connected=True).values('user_id').annotate(
        connected_count=Count('pk'),
    ):
        adoption[row['user_id']]['mailbox']['connected_count'] = row['connected_count']

    return adoption


def product_adoption_summary(customer_users):
    """Return aggregate setup and usage counts without customer content or secrets."""
    profiles = BusinessProfile.objects.filter(user__in=customer_users).annotate(
        trimmed_offer=Trim('what_you_do'),
        trimmed_problem=Trim('problem_you_solve'),
    )
    complete_profiles = profiles.exclude(trimmed_offer='').exclude(trimmed_problem='').count()
    profile_has_data = (
        Q(company_name__gt='') | Q(website__gt='') | Q(industry__gt='')
        | Q(what_you_do__gt='') | Q(problem_you_solve__gt='') | Q(ideal_customer__gt='')
        | Q(differentiator__gt='') | Q(proof_points__gt='') | Q(case_study__gt='')
        | Q(never_claim__gt='') | Q(sender_name__gt='') | Q(sender_title__gt='')
        | ~Q(icp_titles=[]) | ~Q(icp_industries=[]) | ~Q(icp_locations=[])
        | Q(icp_employee_min__isnull=False) | Q(icp_employee_max__isnull=False)
        | Q(icp_requires_funding=True)
    )
    started_profiles = profiles.filter(profile_has_data).exclude(
        trimmed_offer__gt='', trimmed_problem__gt='',
    ).count()

    integrations = APIIntegration.objects.filter(user__in=customer_users, is_active=True).exclude(encrypted_api_key='')
    connected_users = {
        row['provider']: row['users']
        for row in integrations.values('provider').annotate(users=Count('user_id', distinct=True))
    }
    llm_connected_users = integrations.filter(provider__in=LLM_PROVIDER_LABELS).values('user_id').distinct().count()
    recent_jobs = BackgroundJob.objects.filter(
        user__in=customer_users,
        job_type__in=ADOPTION_JOB_TYPES,
        created_at__gte=timezone.now() - timedelta(days=30),
    )
    job_counts = {
        row['job_type']: row['total']
        for row in recent_jobs.values('job_type').annotate(total=Count('pk'))
    }
    return {
        'business_profiles_complete': complete_profiles,
        'business_profiles_started': started_profiles,
        'llm_connected_users': llm_connected_users,
        'apollo_connected_users': connected_users.get('apollo', 0),
        'hunter_connected_users': connected_users.get('hunter', 0),
        'mailbox_connected_users': EmailAccount.objects.filter(
            user__in=customer_users, is_connected=True,
        ).values('user_id').distinct().count(),
        'ai_jobs_30d': sum(job_counts.get(job_type, 0) for job_type in LLM_JOB_TYPES),
        'apollo_searches_30d': job_counts.get('apollo_search', 0),
        'hunter_searches_30d': job_counts.get('hunter_search', 0),
    }
