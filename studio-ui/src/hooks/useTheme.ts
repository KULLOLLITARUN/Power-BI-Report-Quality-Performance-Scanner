import { useCallback, useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';
const KEY = 'pbiscan_theme';

function systemTheme(): Theme {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

/** Follows the OS theme until the user picks one; an explicit pick sets data-theme on <html>. */
export function useTheme() {
  const [explicit, setExplicit] = useState<Theme | null>(() => {
    try {
      const v = localStorage.getItem(KEY);
      return v === 'dark' || v === 'light' ? v : null;
    } catch {
      return null;
    }
  });
  const [system, setSystem] = useState<Theme>(systemTheme);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setSystem(mq.matches ? 'dark' : 'light');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (explicit) root.setAttribute('data-theme', explicit);
    else root.removeAttribute('data-theme');
    try {
      if (explicit) localStorage.setItem(KEY, explicit);
      else localStorage.removeItem(KEY);
    } catch {
      // Storage blocked: the choice lasts for this page load.
    }
  }, [explicit]);

  const theme = explicit ?? system;
  const toggleTheme = useCallback(() => setExplicit(theme === 'dark' ? 'light' : 'dark'), [theme]);
  return { theme, toggleTheme };
}
