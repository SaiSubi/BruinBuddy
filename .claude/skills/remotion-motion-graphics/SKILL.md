---
name: remotion-motion-graphics
source: https://github.com/haidrrrry/claude-remotion-skill
description: Create professional motion graphics videos with Remotion (React-based 30fps frame-by-frame video) using spring physics, compound entrances, staggered kinetic typography, animated counters, and a 5-layer visual stack (Background Mesh, Assets, Kinetic Type/Graphics, Color Grade, Film Grain + Vignette).
---

# Remotion Motion Graphics Skill (`remotion_motion`)

Adapted from [`haidrrrry/claude-remotion-skill`](https://github.com/haidrrrry/claude-remotion-skill) for BruinBuddy's **Illustrate** Studio.

## When to Select `remotion_motion`
- High-impact motion graphics explainers, key takeaways, metric comparisons, formula/concept hooks, multi-card breakdowns, and kinetic typography summaries.
- Whenever a student asks for a "Remotion video", "motion graphics", "kinetic typography", "reel/short explainer", or a punchy visual summary with animated counters and spring transitions.

## 10 Non-Negotiable Motion Graphics Rules
1. **Never use linear interpolation**: Every interpolation uses an exponential/quintic easing curve (`easeOutExpo` `cubic-bezier(0.16, 1, 0.3, 1)`), and entrances use damped harmonic **spring physics** (`damping: 14, stiffness: 160, mass: 0.6`).
2. **Compound entrances**: Animate 2–3 properties simultaneously (`opacity` + `translateY` + `scale`). Lone opacity fades are forbidden.
3. **Stagger everything**: Words, metric cards, and bars enter with `3–6` frame offsets at `30fps`.
4. **Exits are faster than entrances**: ~10 frames out vs ~20 frames in.
5. **Five-layer composition stack in every scene** (bottom to top):
   - Layer 1: **Background Mesh** (drifting radial UCLA Blue & Westwood Navy gradient orbs)
   - Layer 2: **Scene Assets & Metric Cards**
   - Layer 3: **Staggered Kinetic Typography & Animated Counters**
   - Layer 4: **Color Grade**
   - Layer 5: **Procedural Film Grain + Radial Vignette**
6. **Idle elements breathe**: Any element on screen >2s receives continuous sine-wave micro-motion.
7. **Frame-accurate 30fps timeline**: All timing derives from `fps = 30` (`HIT -> hold -> build -> HIT`).
8. **Single UCLA × Remotion theme object**: No inline magic colors; strict zero-emoji rule (only vector SVG/Canvas geometric glyphs).
