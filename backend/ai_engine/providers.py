"""Multi-provider LLM layer.

One interface over OpenAI, Anthropic, and Groq so the rest of the app never
branches on provider. Every provider exposes the same three operations:

    list_models(api_key)              -> live model list from the provider
    validate(api_key, model)          -> (ok, error) after a real round-trip
    generate(api_key, model, ...)     -> completion text

Credentials are never stored here -- callers pass a decrypted key in and it is
used for that call only.
"""
import logging

import anthropic
import openai

logger = logging.getLogger(__name__)

OPENAI = 'openai'
ANTHROPIC = 'anthropic'
GROQ = 'groq'

SUPPORTED_PROVIDERS = (OPENAI, ANTHROPIC, GROQ)

# Groq speaks the OpenAI chat-completions protocol, so it reuses that client
# with a different base URL rather than pulling in a third SDK.
GROQ_BASE_URL = 'https://api.groq.com/openai/v1'


class ProviderError(Exception):
    """A provider rejected the request. `message` is safe to show the user."""

    def __init__(self, message, *, code=None):
        super().__init__(message)
        self.message = message
        self.code = code


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------
# Curated per provider for *this* product's job: short, highly personalised
# cold emails generated one-per-lead. That workload rewards strong instruction
# following and low per-call cost far more than long-context or vision ability.
#
# `recommended` marks the default pick. The live model list from each provider
# is merged over this at request time, so a model released after this file was
# written still shows up -- it just won't carry a description.

PROVIDER_CATALOG = {
    OPENAI: {
        'label': 'OpenAI',
        'key_prefix': 'sk-',
        'console_url': 'https://platform.openai.com/api-keys',
        'models': [
            {
                'id': 'gpt-4o-mini',
                'label': 'GPT-4o mini',
                'recommended': True,
                'note': 'Best cost/quality balance for per-lead drafting. Fast and inexpensive at volume.',
            },
            {
                'id': 'gpt-4o',
                'label': 'GPT-4o',
                'note': 'Higher quality personalisation; noticeably more expensive per lead.',
            },
            {
                'id': 'gpt-4.1-mini',
                'label': 'GPT-4.1 mini',
                'note': 'Strong instruction following at a low price point.',
            },
        ],
    },
    ANTHROPIC: {
        'label': 'Anthropic (Claude)',
        'key_prefix': 'sk-ant-',
        'console_url': 'https://platform.claude.com/settings/keys',
        'models': [
            {
                'id': 'claude-opus-5',
                'label': 'Claude Opus 5',
                'recommended': True,
                'note': 'Highest quality writing and instruction following. Best output, highest cost per lead.',
            },
            {
                'id': 'claude-sonnet-5',
                'label': 'Claude Sonnet 5',
                'note': 'Near-Opus quality at lower cost. A strong default for high-volume sending.',
            },
            {
                'id': 'claude-haiku-4-5',
                'label': 'Claude Haiku 4.5',
                'note': 'Fastest and cheapest. Good for bulk first-touch drafts.',
            },
        ],
    },
    GROQ: {
        'label': 'Groq',
        'key_prefix': 'gsk_',
        'console_url': 'https://console.groq.com/keys',
        'models': [
            {
                'id': 'llama-3.3-70b-versatile',
                'label': 'Llama 3.3 70B',
                'recommended': True,
                'note': 'Strongest open model on Groq. Very fast, very cheap per lead.',
            },
            {
                'id': 'llama-3.1-8b-instant',
                'label': 'Llama 3.1 8B Instant',
                'note': 'Lowest latency and cost. Drafts need more review.',
            },
        ],
    },
}


def catalog():
    """Provider metadata for the settings UI (no credentials involved)."""
    return [
        {
            'provider': provider,
            'label': meta['label'],
            'key_prefix': meta['key_prefix'],
            'console_url': meta['console_url'],
            'models': meta['models'],
        }
        for provider, meta in PROVIDER_CATALOG.items()
    ]


def _curated(provider):
    return {m['id']: m for m in PROVIDER_CATALOG.get(provider, {}).get('models', [])}


# --------------------------------------------------------------------------
# Clients
# --------------------------------------------------------------------------

def _openai_client(api_key, base_url=None):
    return openai.OpenAI(api_key=api_key, base_url=base_url, timeout=30.0, max_retries=1)


def _anthropic_client(api_key):
    return anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=1)


def _friendly_openai_error(exc):
    """Turn an SDK exception into something a user can act on."""
    if isinstance(exc, openai.AuthenticationError):
        return 'Invalid API key. Check the key and try again.'
    if isinstance(exc, openai.PermissionDeniedError):
        return 'This API key does not have access to that model.'
    if isinstance(exc, openai.NotFoundError):
        return 'That model does not exist or is not available to this account.'
    if isinstance(exc, openai.RateLimitError):
        return 'Rate limited or out of quota. Check your billing, then retry.'
    if isinstance(exc, openai.APIConnectionError):
        return 'Could not reach the provider. Check your network and try again.'
    if isinstance(exc, openai.APIStatusError):
        return f'Provider returned an error (HTTP {exc.status_code}).'
    return f'Unexpected error: {exc}'


def _friendly_anthropic_error(exc):
    if isinstance(exc, anthropic.AuthenticationError):
        return 'Invalid API key. Check the key and try again.'
    if isinstance(exc, anthropic.PermissionDeniedError):
        return 'This API key does not have access to that model.'
    if isinstance(exc, anthropic.NotFoundError):
        return 'That model does not exist or is not available to this account.'
    if isinstance(exc, anthropic.RateLimitError):
        return 'Rate limited or out of credit. Check your billing, then retry.'
    if isinstance(exc, anthropic.APIConnectionError):
        return 'Could not reach Anthropic. Check your network and try again.'
    if isinstance(exc, anthropic.APIStatusError):
        return f'Anthropic returned an error (HTTP {exc.status_code}).'
    return f'Unexpected error: {exc}'


# --------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------

def list_models(provider, api_key):
    """Live model IDs from the provider, annotated with curated guidance.

    Falls back to the curated list when the provider has no usable models
    endpoint, so the picker is never empty for a valid key.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ProviderError(f'Unknown provider: {provider}')

    curated = _curated(provider)

    try:
        if provider == ANTHROPIC:
            live_ids = [m.id for m in _anthropic_client(api_key).models.list()]
        else:
            base_url = GROQ_BASE_URL if provider == GROQ else None
            live_ids = [m.id for m in _openai_client(api_key, base_url).models.list()]
    except Exception as exc:
        message = (
            _friendly_anthropic_error(exc) if provider == ANTHROPIC
            else _friendly_openai_error(exc)
        )
        raise ProviderError(message) from exc

    live_ids = _filter_chat_models(provider, live_ids)

    models = []
    for model_id in sorted(live_ids):
        meta = curated.get(model_id, {})
        models.append({
            'id': model_id,
            'label': meta.get('label', model_id),
            'recommended': meta.get('recommended', False),
            'note': meta.get('note', ''),
        })

    # Surface curated picks even if the provider's listing omits them.
    listed = {m['id'] for m in models}
    for model_id, meta in curated.items():
        if model_id not in listed:
            models.append({**meta, 'unverified': True})

    models.sort(key=lambda m: (not m.get('recommended'), m['id']))
    return models


def _filter_chat_models(provider, model_ids):
    """Drop entries that can't serve a chat completion (embeddings, TTS, …)."""
    if provider == ANTHROPIC:
        return model_ids

    skip = ('embedding', 'whisper', 'tts', 'dall-e', 'moderation', 'audio', 'realtime', 'guard')
    return [m for m in model_ids if not any(token in m.lower() for token in skip)]


def validate(provider, api_key, model):
    """Send one real, minimal completion. Returns (ok, error_message).

    A key that lists models can still fail to generate -- wrong model access,
    no credit, org restrictions -- so validation must actually generate.
    """
    if provider not in SUPPORTED_PROVIDERS:
        return False, f'Unknown provider: {provider}'
    if not api_key:
        return False, 'API key is required.'
    if not model:
        return False, 'Select a model.'

    try:
        text = generate(
            provider, api_key, model,
            system_prompt='You are a connectivity check. Reply with the single word: OK',
            user_prompt='Reply with the single word: OK',
            max_tokens=16,
        )
    except ProviderError as exc:
        return False, exc.message
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception('Unexpected error validating %s/%s', provider, model)
        return False, f'Unexpected error: {exc}'

    if not text or not text.strip():
        return False, 'The model returned an empty response. Try a different model.'

    return True, None


def generate(provider, api_key, model, system_prompt, user_prompt, max_tokens=500):
    """Run a completion and return the text. Raises ProviderError on failure."""
    if provider == ANTHROPIC:
        return _generate_anthropic(api_key, model, system_prompt, user_prompt, max_tokens)

    base_url = GROQ_BASE_URL if provider == GROQ else None
    return _generate_openai_compatible(api_key, model, system_prompt, user_prompt, max_tokens, base_url)


def _generate_openai_compatible(api_key, model, system_prompt, user_prompt, max_tokens, base_url):
    try:
        response = _openai_client(api_key, base_url).chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        )
    except Exception as exc:
        raise ProviderError(_friendly_openai_error(exc)) from exc

    choice = response.choices[0] if response.choices else None
    return (choice.message.content or '').strip() if choice else ''


def _generate_anthropic(api_key, model, system_prompt, user_prompt, max_tokens):
    try:
        response = _anthropic_client(api_key).messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
    except Exception as exc:
        raise ProviderError(_friendly_anthropic_error(exc)) from exc

    # Claude can decline a request; that arrives as a 200 with no usable text.
    if getattr(response, 'stop_reason', None) == 'refusal':
        raise ProviderError('The model declined this request.', code='refusal')

    return ''.join(
        block.text for block in response.content if getattr(block, 'type', None) == 'text'
    ).strip()
