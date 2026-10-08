/**
 * Shared API helpers.
 *
 * Access tokens are deliberately short-lived (30 min) so a leaked one expires
 * quickly. That only works if the client can silently exchange its refresh token,
 * which is what authFetch does.
 */

// Production API calls use a dedicated same-origin prefix that Nginx sends to
// Next.js, avoiding stale direct-to-Django Nginx upstreams. Next.js then proxies
// these requests to Django on the server. Local development keeps its override
// and otherwise uses the /api rewrite below.
const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE || "";
export const API_BASE = (
  process.env.NODE_ENV === "production" ? "/backend" : configuredApiBase
).replace(/\/$/, "");

const ACCESS_KEY = "richlead_token";
const REFRESH_KEY = "richlead_refresh";

export function getAccessToken() {
  return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY);
}

export function storeTokens({ access, refresh }) {
  if (access) localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function redirectToLogin() {
  clearTokens();
  if (typeof window !== "undefined") {
    window.location.assign(new URL("/login", window.location.origin));
  }
}

/**
 * Normalise a DRF list response.
 *
 * List endpoints are paginated ({count, next, previous, results}), but some
 * responses are still bare arrays. Returns an array either way so callers
 * never have to branch.
 */
export function asList(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

// Collapses concurrent 401s into a single refresh round-trip.
let refreshInFlight = null;

async function refreshAccessToken() {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return null;

  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE}/api/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    })
      .then(async (res) => {
        if (!res.ok) return null;
        const data = await res.json();
        storeTokens({ access: data.access, refresh: data.refresh });
        return data.access || null;
      })
      .catch(() => null)
      .finally(() => {
        refreshInFlight = null;
      });
  }

  return refreshInFlight;
}

/**
 * fetch() with the bearer token attached, retrying once after a token refresh.
 * Redirects to /login only when the refresh itself fails.
 */
export async function authFetch(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  const send = (token) =>
    fetch(url, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

  let response = await send(getAccessToken());

  if (response.status === 401) {
    const fresh = await refreshAccessToken();
    if (!fresh) {
      redirectToLogin();
      return response;
    }
    response = await send(fresh);
  }

  return response;
}
