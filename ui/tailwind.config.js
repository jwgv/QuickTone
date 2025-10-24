/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Theme tokens use CSS variables so they can switch at runtime
        base: {
          bg: 'rgb(var(--color-base-bg) / <alpha-value>)',
          card: 'rgb(var(--color-base-card) / <alpha-value>)',
          hover: 'rgb(var(--color-base-hover) / <alpha-value>)',
          border: 'rgb(var(--color-base-border) / <alpha-value>)'
        },
        primary: {
          DEFAULT: '#60a5fa',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb'
        },
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444'
      },
    },
  },
  plugins: [],
}
