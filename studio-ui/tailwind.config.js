/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        studio: {
          bg: '#090A0F',
          sidebar: '#0E1017',
          card: '#131620',
          cardHover: '#181C28',
          border: '#1F2433',
          borderLight: '#2D3449',
          subtle: '#64748B',
          text: '#F1F5F9',
          textMuted: '#94A3B8',
        },
        brand: {
          blue: '#2563EB',
          blueHover: '#1D4ED8',
          emerald: '#10B981',
          amber: '#F59E0B',
          red: '#EF4444',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Cascadia Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
