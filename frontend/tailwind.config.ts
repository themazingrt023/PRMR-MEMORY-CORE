import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./data/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#090909",
        void: "#090909",
        charcoal: "#0b0b0b",
        graphite: "#121212",
        steel: "#7f8790",
        silver: "#cfd5dc",
        mist: "#f2f5f7",
        frost: "#e8eef5",
        bluewhite: "#b9d7ff"
      },
      fontFamily: {
        display: ["Georgia", "Times New Roman", "serif"],
        body: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      boxShadow: {
        silver: "0 0 42px rgba(210, 224, 238, 0.16)"
      }
    }
  },
  plugins: []
};

export default config;
