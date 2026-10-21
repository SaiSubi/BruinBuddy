---
name: anatomy
description: Build crafted, interactive isometric SVG figures that explain a technical or course concept as a real physical object or apparatus (e.g., Galton board, urn sampler, balance scale, filter gate, dial gauge), with four-tone shaded solid parts, painter's order, framed card with title/hint/live readout, and interactive parameter sliders. Adapted from wheresryan22/anatomy for BruinBuddy's Illustrate engine.
source: https://github.com/wheresryan22/anatomy
license: MIT
---

# Anatomy — Interactive Isometric Apparatus Skill

## Core Philosophy
Explain an abstract idea by inventing a concrete physical apparatus whose mechanism *is* the concept:
- **Probability & Statistics:** A Galton board (bean machine) with adjustable peg bias $p$, an urn-drawing mechanism with replacement toggle, a two-stage Bayes filter gate where particles pass through conditional apertures, or a balance beam showing expectation $E[X]$ as the center of mass.
- **Systems & CS:** A token bucket rate limiter with a drip valve, a pin-tumbler cache lock, or a sliding-window conveyor belt.

## Visual & Craft Rules
1. **True Isometric Projection:**
   - Ground axes run at $\pm 30^\circ$ from horizontal (`cos(30°) = 0.866`, `sin(30°) = 0.5`), vertical axis $Z$ runs straight up (`(0, -1)`).
   - Projection helper: `iso(x, y, z) => ({ sx: cx + (x - y) * 0.866 * scale, sy: cy + (x + y) * 0.5 * scale - z * scale })`.
   - Parallel projection only (no vanishing-point perspective distortion).
2. **Four-Tone Solid Shading:**
   - Top face: brightest (`L + 12%`)
   - Left face (lit): medium-bright (`L`)
   - Right face (shadow): darker (`L - 16%`)
   - Base/recess/cutout: deepest shadow (`L - 28%`)
   - Crisp `1px` or `1.2px` stroke matching the material's dark edge.
3. **Painter's Order (Back-to-Front):**
   - Sort 3D solids by depth key `(x + y - z * 0.5)` from back to front so foreground parts cleanly occlude background parts.
4. **Framed Instrument Card + Live Mathematical Model:**
   - Every figure sits in a clean framed card with:
     - **Header:** `Fig. 1 · <Title>` and a live numeric readout badge driven by the same mathematical model that moves the parts.
     - **Interactive Controls:** 1–3 smooth sliders or toggle buttons (e.g., parameter $p$, sample size $n$, threshold $t$) plus Play/Pause & Reset.
     - **Caption / Hint:** 1–2 concise sentences connecting the moving mechanism to the course formula.
