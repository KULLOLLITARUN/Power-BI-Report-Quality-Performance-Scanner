// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// api.ts reads the token once, when it is first imported, so each case loads a fresh copy.
async function loadApi() {
  vi.resetModules();
  return import('./api');
}

describe('hasStudioToken', () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState(null, '', '/');
  });
  afterEach(() => {
    sessionStorage.clear();
    window.history.replaceState(null, '', '/');
  });

  it('is false on a page opened without the token (a hosted copy)', async () => {
    const api = await loadApi();
    expect(api.hasStudioToken()).toBe(false);
  });

  it('is true when the page was opened from the URL `pbiscan studio` prints', async () => {
    window.history.replaceState(null, '', '/?token=abc123');
    const api = await loadApi();
    expect(api.hasStudioToken()).toBe(true);
    expect(window.location.search).toBe(''); // the token is moved out of the address bar
  });

  it('stays true after a reload of the same tab', async () => {
    window.history.replaceState(null, '', '/?token=abc123');
    await loadApi();
    window.history.replaceState(null, '', '/');
    const api = await loadApi();
    expect(api.hasStudioToken()).toBe(true);
  });
});
