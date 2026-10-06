// Studio API access. `pbiscan studio` generates a random token per run and opens
// the browser at /?token=...; every /api/* call except /api/health must send it
// back in the X-PBIScan-Token header (see local_origin_guard in pbiscan/server.py).
// The token is moved out of the address bar into sessionStorage so it doesn't
// linger in history or bookmarks, and survives reloads of this tab.

const TOKEN_PARAM = 'token';
const TOKEN_STORAGE_KEY = 'pbiscan_studio_token';
export const TOKEN_HEADER = 'X-PBIScan-Token';

function captureToken(): string | null {
  let token: string | null = null;
  try {
    const url = new URL(window.location.href);
    token = url.searchParams.get(TOKEN_PARAM);
    if (token) {
      url.searchParams.delete(TOKEN_PARAM);
      window.history.replaceState(window.history.state, '', url.toString());
    }
  } catch {
    // No usable location (tests, unusual embedding): fall through to storage.
  }
  try {
    if (token) sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    else token = sessionStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    // Storage blocked: the token still works for this page load.
  }
  return token;
}

const studioToken = captureToken();

/** fetch() for Studio's own API, with the per-run access token attached. */
export function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (studioToken) headers.set(TOKEN_HEADER, studioToken);
  return fetch(input, { ...init, headers });
}
