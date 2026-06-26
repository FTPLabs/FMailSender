/** @type {import('tailwindcss').Config} */
  export default {
    content: ['./index.html', './src/**/*.{ts,tsx}'],
    theme: {
      extend: {
        colors: {
          base:    '#040410',
          surface: '#0d1117',
          surf2:   '#141424',
          surf3:   '#1c1c35',
          purple:  { DEFAULT: '#8b5cf6', light: '#a78bfa', dark: '#7c3aed' },
          cyan:    { DEFAULT: '#06b6d4', light: '#22d3ee', dark: '#0891b2' },
          text:    { DEFAULT: '#e8e8ff', muted: '#6666aa', dim: '#3a3a66' },
          success: '#10b981',
          error:   '#ef4444',
          warn:    '#f59e0b',
        },
        fontFamily: {
          sans: ['Inter', 'system-ui', 'sans-serif'],
          mono: ['JetBrains Mono', 'monospace'],
        },
        boxShadow: {
          'glow-purple': '0 0 24px rgba(139,92,246,.35)',
          'glow-cyan':   '0 0 24px rgba(6,182,212,.35)',
          'glow-sm':     '0 0 12px rgba(139,92,246,.2)',
        },
        animation: {
          'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          'spin-slow':  'spin 8s linear infinite',
          'fade-in':    'fadeIn 0.3s ease',
        },
        keyframes: {
          fadeIn: { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'none' } },
        },
      },
    },
    plugins: [],
  }
  