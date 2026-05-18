import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        mist: "#f3f4f6",
        accent: "#0f766e",
        ember: "#b45309",
        slateblue: "#1d4ed8",
      },
      boxShadow: {
        panel: "0 18px 40px rgba(17, 24, 39, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
