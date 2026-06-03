import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#0a0a0f',
        surface: '#13131f',
        border: 'rgba(255,255,255,0.06)',
        cyan: '#00d4ff',
        amber: '#ffb347',
        emerald: '#00c785',
        muted: '#94a3b8',
        dim: '#64748b',
        accent: '#e2b84d',
        'accent-dim': '#c9a33e',
      },
      fontFamily: {
        sans: ['Geist Sans', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
