// UCLA Bruin Learn × Remotion single source of truth theme
import { Easing } from "remotion";

export const theme = {
  colors: {
    bg: "#0A0E17",
    bgAlt: "#121C2B",
    primary: "#2774AE", // UCLA Blue — hero color
    accent: "#FFD100",  // UCLA Gold — single focal accent
    text: "#F4F6F9",
    textDim: "#9EB0C2",
    glow: "rgba(39, 116, 174, 0.42)",
  },
  fonts: {
    display: "Inter",
    body: "Inter",
    mono: "JetBrains Mono",
  },
  ease: {
    out: Easing.bezier(0.16, 1, 0.3, 1),    // easeOutExpo — entrances
    inOut: Easing.bezier(0.83, 0, 0.17, 1), // easeInOutQuint — moves
    in: Easing.bezier(0.7, 0, 0.84, 0),     // exits only
  },
  spring: {
    snappy: { damping: 14, stiffness: 160, mass: 0.6 },
    smooth: { damping: 20, stiffness: 90, mass: 1.0 },
    bouncy: { damping: 11, stiffness: 170, mass: 0.7 },
  },
} as const;
