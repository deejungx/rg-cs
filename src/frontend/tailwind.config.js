/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        moss: {
          50: "#f5f6ef",
          100: "#e7eadc",
          200: "#cfd6bf",
          300: "#b3bd9b",
          400: "#93a070",
          500: "#758353",
          600: "#5d6a42",
          700: "#4a5437",
          800: "#3e4531",
          900: "#353b2b"
        },
        ember: {
          100: "#fff0dc",
          200: "#ffd8a8",
          500: "#c56a1b",
          700: "#8c4610"
        }
      },
      fontFamily: {
        display: ["Space Grotesk", "Segoe UI", "sans-serif"],
        body: ["Space Grotesk", "Segoe UI", "sans-serif"]
      },
      boxShadow: {
        glass: "0 18px 60px rgba(53, 73, 63, 0.12)"
      }
    },
  },
  plugins: [],
};
