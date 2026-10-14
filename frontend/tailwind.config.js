/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef7ff',
          100: '#d9edff',
          500: '#2563eb',
          700: '#1d4ed8',
          900: '#172554',
        },
      },
    },
  },
  plugins: [],
};
