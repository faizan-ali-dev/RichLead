"""Small cache-aside helpers for optional, tenant-safe Redis caching."""

import hashlib
import json
import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


def make_cache_key(namespace, parts):
    """Hash cache inputs so keys never expose tenant data or provider credentials."""
    safe_namespace = re.sub(r"[^a-zA-Z0-9_-]", "_", namespace)[:40]
    serialized = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"richlead:v1:{safe_namespace}:{digest}"


def cache_call(namespace, *, parts, timeout, producer):
    """Return a cached value or compute it; caching failures never fail the request."""
    if not getattr(settings, "CACHE_ENABLED", False) or timeout <= 0:
        return producer()

    key = make_cache_key(namespace, parts)
    try:
        cached_value = cache.get(key)
    except Exception:
        logger.warning("Cache read failed for %s; bypassing cache.", namespace)
        return producer()

    if cached_value is not None:
        logger.debug("Cache hit for %s.", namespace)
        return cached_value

    value = producer()
    if value is None:
        return value
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        logger.warning("Cache write failed for %s; returning fresh data.", namespace)
    return value


def dashboard_stats_cache_key(user_id, day=None):
    return make_cache_key("dashboard-stats", {
        "user_id": user_id,
        "day": (day or timezone.localdate()).isoformat(),
    })


def invalidate_dashboard_stats(user_id):
    """Invalidate only this tenant's current dashboard window."""
    if not getattr(settings, "CACHE_ENABLED", False):
        return
    try:
        cache.delete(dashboard_stats_cache_key(user_id))
    except Exception:
        logger.warning("Dashboard cache invalidation failed; TTL will expire the entry.")
