/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        plane: '#0a0b0f',
        surface: '#12141a',
        'surface-2': '#181b22',
        'surface-3': '#1f232c',
        hairline: 'rgba(255,255,255,0.08)',
        ink: {
          primary: '#ffffff',
          secondary: '#c3c2b7',
          muted: '#7d818c',
        },
        status: {
          good: '#0ca30c',
          warning: '#fab219',
          critical: '#d03b3b',
        },
        camA: '#5b7a99',
        camB: '#a67c52',
        series: {
          1: '#3987e5',
          2: '#d95926',
          3: '#199e70',
          4: '#c98500',
          5: '#d55181',
          6: '#008300',
          7: '#9085e9',
          8: '#e66767',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
