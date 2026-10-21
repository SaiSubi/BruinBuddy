---
name: explainer-video
description: Script, storyboard, and animate progressive diagrams, flowcharts, and whiteboard draw-on explainers. Combines explainer-video, diagram-animation, whiteboard-animation, and isometric-animation from iart-ai/explainer-video-skills for BruinBuddy's Illustrate engine.
source: https://github.com/iart-ai/explainer-video-skills
license: MIT
---

# Explainer Video & Progressive Diagram Skill

Combines four sub-skills from `iart-ai/explainer-video-skills`:
1. **`explainer-video`** — 4-beat narrative arc (Problem/Question $\to$ Core Idea $\to$ Step-by-Step Mechanism $\to$ Takeaway) with synchronized captions timed at $\approx 2.3\text{ words/sec}$.
2. **`diagram-animation`** — Progressive disclosure (**nodes $\to$ edges $\to$ labels**), `pathLength="1"` `stroke-dashoffset` connectors, marching-dash flow packets, and focus dimming (`opacity: 0.35` on inactive nodes).
3. **`whiteboard-animation`** — Stroke-by-stroke SVG draw-on (`stroke-dashoffset: 1 -> 0`) tracked by a moving pen nib (`getPointAtLength`), revealing diagrams and handwritten formulas in narration order.
4. **`isometric-animation`** — Stacked 2.5D layers (`rotateX(60deg) rotateZ(45deg)` or SVG isometric planes) that reveal bottom-up with staggered easing.

## Core Rules
- **Progressive Disclosure:** Never dump the full diagram on frame 1. Reveal one node, edge, or step per beat (0.8–1.5s per beat) while updating the synchronized caption bar below the canvas.
- **Focus + Context:** The active beat's node/step is highlighted at full opacity (`1.0`) with an accent glow, while previously revealed steps stay visible at `0.85` and future steps remain hidden (`0.0` or `0.15`).
- **Muted-First Captions:** Every beat displays a crisp, readable caption banner synced to the timeline scrubber so students studying in a library or classroom understand the animation without audio.
