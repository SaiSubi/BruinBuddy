---
name: manim
description: Create 3Blue1Brown-style mathematical animations combining manim-composer narrative planning and manimce-best-practices visual grammar. Used by BruinBuddy's Illustrate engine to render dynamic probability distributions, calculus integrals, linear algebra transformations, and equation morphs both in-browser (HTML5 Canvas/SVG) and as runnable Manim Community Edition Python scripts.
source: https://github.com/adithya-s-k/manim_skill
license: MIT
---

# Manim (3Blue1Brown Style) — Math Animation Skill

Combines `manim-composer` (narrative arc & scene planning) and `manimce-best-practices` (3Blue1Brown visual palette, coordinate axes, `ValueTracker` sweeps, and `from manim import *` code generation).

## 1. Narrative Arc (`manim-composer`)
1. **Hook / Question:** Start with the visual intuition before showing dense notation.
2. **Geometric / Visual Build:** Draw axes (`Axes`), curves (`plot`), bars (`BarChart`), or probability regions (`get_area`) progressively.
3. **Dynamic Parameter Sweep (`ValueTracker`):** Animate a key parameter (e.g., $\mu, \sigma, n, p$, integration bound $b$, or prior $P(A)$) so the student sees how the curve, area, and formula respond in real time.
4. **Key Insight ("Aha Moment"):** Highlight the invariant or relationship using color-coded terms matching the geometric shapes.

## 2. 3Blue1Brown Visual Grammar (`manimce-best-practices`)
- **Background:** Deep slate `#14181a` / `#1c2124` for high contrast.
- **Canonical Color Palette (Color = Meaning):**
  - `BLUE_C` (`#58C4DD`): Primary function / distribution / prior $P(A)$
  - `YELLOW` (`#FFFF00`): Highlighted parameter / active tracker / moving point
  - `GREEN_C` (`#83C167`): Target region / integral area / likelihood $P(B|A)$
  - `RED_C` (`#FC6255`): Comparison curve / rejection region / error / complement
  - `TEAL_C` (`#5CD0B3`): Secondary curve / posterior result
- **Pacing & Easing:**
  - Smooth cubic ease-in-out (`smooth(t)`) for curve drawing and morphs.
  - Hold 1.0–1.5s between beats so equations and visual regions register together.
- **Dual Output:**
  - **In-Browser Interactive 3B1B Player:** Renders the multi-beat mathematical animation at 60fps on HTML5 Canvas/SVG with live parameter sliders, play/pause, timeline scrubber, and WebM/PNG export.
  - **Runnable ManimCE Script (`.py`):** Also provides valid `from manim import *` (`class ConceptScene(Scene): ...`) code following `manimce-best-practices`.
