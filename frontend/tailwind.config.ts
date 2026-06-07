/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist Sans', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'monospace'],
        display: ['Fraunces', 'serif'],
        heading: ['Syne', 'sans-serif'],
      },
      colors: {
        void: '#0a0a0f',
        surface: '#13131f',
        border: 'rgba(255,255,255,0.06)',
        cyan: '#00d4ff',
        amber: '#ffb347',
        emerald: '#00c785',
        muted: '#94a3b8',
        dim: '#64748b',
        gold: '#f0c040',
        rose: '#f04060',
        sage: '#60d4a0',
        violet: '#a060f0',
      },
      maxWidth: {
        content: '1280px',
      },
    },
  },
  plugins: [],
}
