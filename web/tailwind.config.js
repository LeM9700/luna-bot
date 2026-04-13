/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        luna: {
          50:  '#f0f0ff',
          100: '#e0e0ff',
          500: '#7c6fff',
          600: '#6b5eff',
          700: '#5a4dee',
          900: '#1a1533',
        }
      }
    }
  },
  plugins: []
}
