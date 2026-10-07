// Attributes and style keys React's types leave out but Studio uses.
import 'react';

declare module 'react' {
  interface InputHTMLAttributes<T> {
    /** Folder picker (Chromium, WebKit, Firefox); `directory` is the older spelling. */
    webkitdirectory?: string;
    directory?: string;
  }
  interface CSSProperties {
    /** CSS custom properties, e.g. style={{ '--w': '40%' }}. */
    [key: `--${string}`]: string | number | undefined;
  }
}
