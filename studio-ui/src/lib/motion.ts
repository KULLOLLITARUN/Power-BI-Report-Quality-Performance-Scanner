import anime from 'animejs';

export const prefersReducedMotion = (): boolean => {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
};

/** anime() that does nothing when the viewer prefers reduced motion. Elements must already be visible at rest. */
export function animate(params: anime.AnimeParams): anime.AnimeInstance | null {
  if (prefersReducedMotion()) return null;
  return anime(params);
}

export { anime };
