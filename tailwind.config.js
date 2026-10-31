/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        tinker: {
          yellow: '#F4C761',
          'yellow-hover': '#e8ba4b',
          'yellow-light': '#FFF8EA',
          lime: '#C3FF16',
          'lime-soft': '#F4FEDB',
          purple: '#5E1DB0',
          'purple-light': '#884BD4',
          'purple-soft': '#F5EFFC',
          green: '#3CD377',
          'green-soft': '#ECFDF3',
          blue: '#479CFF',
          'blue-soft': '#EDF5FF',
          dark: '#121316',
          black: '#0A0A0A',
          border: '#1E1E1E',
          surface: '#FFFFFF',
          canvas: '#F9F8F5',
          muted: '#6B7280'
        }
      },
      boxShadow: {
        'neo': '3px 3px 0px #121316',
        'neo-sm': '2px 2px 0px #121316',
        'neo-lg': '5px 5px 0px #121316',
        'neo-yellow': '3px 3px 0px #F4C761',
        'neo-purple': '3px 3px 0px #5E1DB0',
        'neo-green': '3px 3px 0px #3CD377',
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', 'sans-serif'],
        display: ['Anton', 'Cabinet Grotesk', 'Plus Jakarta Sans', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
