/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base:    'rgb(var(--c-base) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        surf2:   'rgb(var(--c-surf2) / <alpha-value>)',
        surf3:   'rgb(var(--c-surf3) / <alpha-value>)',
        dim:     'rgb(var(--c-dim) / <alpha-value>)',
        muted:   'rgb(var(--c-muted) / <alpha-value>)',
        purple:  { DEFAULT: 'rgb(var(--c-accent) / <alpha-value>)', light: 'rgb(var(--c-accent-light) / <alpha-value>)', dark: 'rgb(var(--c-accent-dark) / <alpha-value>)' },
        cyan:    { DEFAULT: 'rgb(var(--c-signal) / <alpha-value>)', light: 'rgb(var(--c-signal-light) / <alpha-value>)', dark: 'rgb(var(--c-signal-dark) / <alpha-value>)' },
        text:    { DEFAULT: 'rgb(var(--c-text) / <alpha-value>)', muted: 'rgb(var(--c-muted) / <alpha-value>)', dim: 'rgb(var(--c-dim) / <alpha-value>)' },
        success: 'rgb(var(--c-success) / <alpha-value>)',
        error:   'rgb(var(--c-error) / <alpha-value>)',
        warn:    'rgb(var(--c-warn) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['"Segoe UI"', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Georgia', '"Times New Roman"', 'serif'],
        mono: ['Consolas', '"Courier New"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'glow-purple': '0 0 32px rgb(var(--c-accent) / .24)',
        'glow-cyan':   '0 0 28px rgb(var(--c-signal) / .20)',
        'glow-sm':     '0 9px 26px rgb(var(--c-accent) / .15)',
        'nocturne':    '0 18px 46px rgb(0 0 0 / .18)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn .32s cubic-bezier(.2,.8,.2,1)',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'none' } },
      },
    },
  },
  plugins: [],
}
