"""Concept illustration engine: routes a chat concept to the best visual skill
(Anatomy isometric apparatus, Manim 3B1B math animation, Progressive Diagram, or Whiteboard Explainer),
builds a self-contained interactive HTML/SVG/Canvas animation + optional ManimCE script, and enforces
solution leak guards on Graded problem sets."""
import html
import json
import re

from . import config, llm
from .db import db, now
from .knowledge import CourseKnowledge
from .retrieval import solution_chunks_for
from .tutor import _llm_leak, _retrieve

SKILLS = ("anatomy_isometric", "manim_3b1b", "explainer_diagram", "explainer_storyboard")

SKILL_META = {
    "anatomy_isometric": {
        "label": "Anatomy Isometric",
        "repo": "wheresryan22/anatomy",
        "modality": "interactive_animation",
        "modality_label": "Interactive Isometric Apparatus",
    },
    "manim_3b1b": {
        "label": "Manim 3B1B",
        "repo": "adithya-s-k/manim_skill",
        "modality": "math_video",
        "modality_label": "3Blue1Brown Math Animation",
    },
    "explainer_diagram": {
        "label": "Diagram Animation",
        "repo": "iart-ai/explainer-video-skills",
        "modality": "animated_diagram",
        "modality_label": "Progressive Animated Diagram",
    },
    "explainer_storyboard": {
        "label": "Explainer Video",
        "repo": "iart-ai/explainer-video-skills",
        "modality": "explainer_video",
        "modality_label": "Whiteboard Explainer Video",
    },
}

ROUTE_SYSTEM = """You are the Visual Skill Router for BruinBuddy, an AI university course tutor.
Given a student-tutor conversation excerpt and course material excerpts, choose the single best visual skill to illustrate the concept being discussed:

1. "manim_3b1b" (from adithya-s-k/manim_skill):
   Choose for mathematical functions, calculus integrals, probability distributions (Normal, Binomial, Poisson, PDF/CDF), Bayes' theorem area squares, Central Limit Theorem, linear algebra, or equation transformations.
2. "anatomy_isometric" (from wheresryan22/anatomy):
   Choose for physical mechanisms, experimental apparatuses, probability machines (Galton board / bean machine, urn drawing, coin/dice rigs, signal filters, queues, buckets), or system architectures that work like a physical instrument.
3. "explainer_diagram" (from iart-ai/explainer-video-skills diagram-animation):
   Choose for step-by-step processes, decision trees, Markov chains, hypothesis testing workflows (H0 -> test statistic -> p-value -> conclusion), or multi-node flowcharts.
4. "explainer_storyboard" (from iart-ai/explainer-video-skills explainer-video & whiteboard-animation):
   Choose for high-level conceptual overviews, definitions, intuition builders, or stroke-by-stroke whiteboard walkthroughs.

Reply with JSON only:
{
  "skill": "manim_3b1b" | "anatomy_isometric" | "explainer_diagram" | "explainer_storyboard",
  "concept": "Short name of the concept (max 60 chars)",
  "title": "Engaging visual title (max 70 chars)",
  "rationale": "One sentence explaining why this visual skill and modality best explains the concept."
}"""

GEN_SYSTEM = """You are the Visual Animation Architect for BruinBuddy.
Generate a rich, accurate educational animation specification in JSON for the selected skill "{skill}" ({skill_label}).
{graded_note}

 strictly output a single valid JSON object matching this schema:
{{
  "title": "Title of the figure/animation",
  "subtitle": "1-sentence intuition or core takeaway",
  "formula": "Key mathematical relation or invariant in plain/LaTeX-like notation (e.g. P(A|B) = P(B|A)P(A) / P(B))",
  "template": "distribution" | "bayes_square" | "clt_galton" | "integral_area" | "isometric_rig" | "flow_diagram" | "whiteboard_story",
  "param_label": "Name of interactive parameter (e.g. 'Probability p', 'Mean μ', 'Sample size n', 'Prior P(H)')",
  "param_min": 0.1,
  "param_max": 0.9,
  "param_step": 0.05,
  "param_default": 0.5,
  "secondary_label": "Second interactive parameter (e.g. 'Spread σ' or 'Trials N')",
  "secondary_min": 1,
  "secondary_max": 20,
  "secondary_step": 1,
  "secondary_default": 8,
  "beats": [
    {{
      "step": 1,
      "heading": "Short beat title (max 40 chars)",
      "caption": "Spoken-style narration caption for this beat (15-28 words, clear and concrete).",
      "highlight": "Key quantity or relationship shown in this beat",
      "value_hint": 0.35
    }},
    {{
      "step": 2,
      "heading": "Beat 2 title",
      "caption": "Second beat narration explaining the mechanism or transformation.",
      "highlight": "Key formula term",
      "value_hint": 0.55
    }},
    {{
      "step": 3,
      "heading": "Beat 3 title",
      "caption": "Third beat narration showing how changing the parameter shifts the outcome.",
      "highlight": "Dynamic effect",
      "value_hint": 0.75
    }},
    {{
      "step": 4,
      "heading": "Beat 4 title",
      "caption": "Final takeaway connecting the visual back to the course concept.",
      "highlight": "Core invariant",
      "value_hint": 0.5
    }}
  ],
  "nodes": [
    {{"id": "n1", "label": "Step 1", "sub": "Input / Prior", "color": "#58C4DD"}},
    {{"id": "n2", "label": "Step 2", "sub": "Mechanism / Likelihood", "color": "#FFFF00"}},
    {{"id": "n3", "label": "Step 3", "sub": "Filter / Transform", "color": "#83C167"}},
    {{"id": "n4", "label": "Step 4", "sub": "Output / Posterior", "color": "#5CD0B3"}}
  ]
}}"""

GRADED_NOTE = (
    "IMPORTANT ACADEMIC INTEGRITY RULE: This chat concerns a GRADED problem set ({pset_title}). "
    "You MUST illustrate only the general underlying concept with synthetic example numbers. "
    "Do NOT reveal final answers, exact numeric results, or solution steps for the assigned problem."
)


def heuristic_skill(text: str) -> str:
    """Fast keyword fallback if the model omits a valid skill name."""
    low = text.lower()
    if any(w in low for w in ("galton", "urn", "machine", "apparatus", "bucket", "filter", "coin", "dice", "rig", "isometric", "physical")):
        return "anatomy_isometric"
    if any(w in low for w in ("workflow", "flowchart", "pipeline", "hypothesis test", "markov", "decision tree", "step by step", "state")):
        return "explainer_diagram"
    if any(w in low for w in ("whiteboard", "story", "overview", "intuition", "summary", "explain like")):
        return "explainer_storyboard"
    return "manim_3b1b"


def _default_template_for_skill(skill: str, concept: str) -> str:
    low = concept.lower()
    if skill == "anatomy_isometric":
        if "galton" in low or "binomial" in low or "central limit" in low:
            return "clt_galton"
        return "isometric_rig"
    if skill == "manim_3b1b":
        if "bayes" in low or "conditional" in low:
            return "bayes_square"
        if "integral" in low or "area" in low or "cdf" in low:
            return "integral_area"
        return "distribution"
    if skill == "explainer_diagram":
        return "flow_diagram"
    return "whiteboard_story"


def _normalize_spec(raw_spec: dict, skill: str, concept: str, title: str) -> dict:
    """Ensure all required fields and beats exist with safe bounds so the animation player never crashes."""
    template = raw_spec.get("template")
    if template not in ("distribution", "bayes_square", "clt_galton", "integral_area", "isometric_rig", "flow_diagram", "whiteboard_story"):
        template = _default_template_for_skill(skill, concept)

    beats = raw_spec.get("beats")
    if not isinstance(beats, list) or len(beats) < 2:
        beats = [
            {
                "step": 1,
                "heading": "1. Core Setup",
                "caption": f"We start by framing {concept} and identifying the key quantities that govern the system.",
                "highlight": "Initial State",
                "value_hint": 0.3,
            },
            {
                "step": 2,
                "heading": "2. Visual Mechanism",
                "caption": "Watch how each contribution accumulates—the geometry directly mirrors the mathematical definition.",
                "highlight": "Accumulation",
                "value_hint": 0.5,
            },
            {
                "step": 3,
                "heading": "3. Parameter Sensitivity",
                "caption": "Use the interactive sliders to shift the parameter and observe how the shape and readout respond.",
                "highlight": "Dynamic Shift",
                "value_hint": 0.75,
            },
            {
                "step": 4,
                "heading": "4. Key Takeaway",
                "caption": "Total probability is conserved while the distribution shifts between outcomes.",
                "highlight": "Invariant",
                "value_hint": 0.5,
            },
        ]
    clean_beats = []
    for idx, b in enumerate(beats[:6], start=1):
        if not isinstance(b, dict):
            continue
        clean_beats.append({
            "step": idx,
            "heading": str(b.get("heading") or f"Step {idx}")[:60],
            "caption": str(b.get("caption") or f"Step {idx} of {concept}.")[:240],
            "highlight": str(b.get("highlight") or concept)[:60],
            "value_hint": float(b.get("value_hint", 0.5)) if isinstance(b.get("value_hint"), (int, float)) else 0.5,
        })

    nodes = raw_spec.get("nodes")
    if not isinstance(nodes, list) or len(nodes) < 3:
        nodes = [
            {"id": "n1", "label": "Prior / Input", "sub": "Initial assumption", "color": "#58C4DD"},
            {"id": "n2", "label": "Mechanism", "sub": "Likelihood / Transform", "color": "#FFFF00"},
            {"id": "n3", "label": "Evidence", "sub": "Observed data", "color": "#83C167"},
            {"id": "n4", "label": "Outcome", "sub": "Updated result", "color": "#5CD0B3"},
        ]
    clean_nodes = []
    palette = ["#58C4DD", "#FFFF00", "#83C167", "#5CD0B3", "#FC6255"]
    for idx, n in enumerate(nodes[:5]):
        if not isinstance(n, dict):
            continue
        clean_nodes.append({
            "id": str(n.get("id") or f"n{idx+1}"),
            "label": str(n.get("label") or f"Stage {idx+1}")[:36],
            "sub": str(n.get("sub") or "")[:48],
            "color": str(n.get("color") or palette[idx % len(palette)]),
        })

    p_min = float(raw_spec.get("param_min", 0.1)) if isinstance(raw_spec.get("param_min"), (int, float)) else 0.1
    p_max = float(raw_spec.get("param_max", 0.9)) if isinstance(raw_spec.get("param_max"), (int, float)) else 0.9
    if p_max <= p_min:
        p_min, p_max = 0.1, 0.9
    p_def = float(raw_spec.get("param_default", (p_min + p_max) / 2)) if isinstance(raw_spec.get("param_default"), (int, float)) else (p_min + p_max) / 2
    p_def = max(p_min, min(p_max, p_def))

    s_min = float(raw_spec.get("secondary_min", 2)) if isinstance(raw_spec.get("secondary_min"), (int, float)) else 2
    s_max = float(raw_spec.get("secondary_max", 16)) if isinstance(raw_spec.get("secondary_max"), (int, float)) else 16
    if s_max <= s_min:
        s_min, s_max = 2, 16
    s_def = float(raw_spec.get("secondary_default", 8)) if isinstance(raw_spec.get("secondary_default"), (int, float)) else 8
    s_def = max(s_min, min(s_max, s_def))

    return {
        "title": str(raw_spec.get("title") or title)[:80],
        "subtitle": str(raw_spec.get("subtitle") or f"Interactive visual explanation of {concept}")[:160],
        "formula": str(raw_spec.get("formula") or "E[X] = ∑ x · P(X = x)")[:100],
        "skill": skill,
        "skill_meta": SKILL_META[skill],
        "template": template,
        "param_label": str(raw_spec.get("param_label") or "Parameter p")[:40],
        "param_min": p_min,
        "param_max": p_max,
        "param_step": float(raw_spec.get("param_step", round((p_max - p_min) / 20, 3))) or 0.05,
        "param_default": p_def,
        "secondary_label": str(raw_spec.get("secondary_label") or "Complexity / Trials N")[:40],
        "secondary_min": s_min,
        "secondary_max": s_max,
        "secondary_step": float(raw_spec.get("secondary_step", 1)) or 1,
        "secondary_default": s_def,
        "beats": clean_beats,
        "nodes": clean_nodes,
    }


def build_manim_code(spec: dict) -> str:
    """Generate a ready-to-run Manim Community Edition (manimce-best-practices) Python script for this concept."""
    title = spec["title"].replace('"', '\\"')
    subtitle = spec["subtitle"].replace('"', '\\"')
    formula = spec["formula"].replace('"', '\\"')
    beats_py = ",\n            ".join(
        f'("{b["heading"].replace(chr(34), "")}", "{b["caption"].replace(chr(34), "")}")'
        for b in spec["beats"]
    )
    return f'''"""Manim Community Edition scene generated by BruinBuddy (adithya-s-k/manim_skill).
Run locally with:
    manim -pql bruinbuddy_scene.py ConceptIllustrationScene
"""
from manim import *
import numpy as np


class ConceptIllustrationScene(Scene):
    def construct(self):
        self.camera.background_color = "#14181a"

        # 1. Title & Header (manimce-best-practices)
        title = Text("{title}", font_size=34, color=WHITE).to_edge(UP, buff=0.35)
        subtitle = Text("{subtitle}", font_size=20, color=GREY_B).next_to(title, DOWN, buff=0.15)
        self.play(Write(title), FadeIn(subtitle, shift=UP * 0.2), run_time=1.2)

        # 2. Coordinate Axes & Dynamic ValueTracker
        axes = Axes(
            x_range=[-3.5, 3.5, 1],
            y_range=[0, 0.55, 0.1],
            x_length=8.5,
            y_length=3.6,
            axis_config={{"color": GREY_B, "include_tip": True}},
        ).shift(DOWN * 0.35)
        axes_labels = axes.get_axis_labels(x_label="x", y_label="f(x)")

        mu_tracker = ValueTracker(0.0)
        sigma_tracker = ValueTracker(1.0)

        def pdf(x):
            mu = mu_tracker.get_value()
            sig = max(0.35, sigma_tracker.get_value())
            return (1.0 / (sig * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mu) / sig) ** 2)

        curve = always_redraw(
            lambda: axes.plot(pdf, color=BLUE_C, stroke_width=4)
        )
        area = always_redraw(
            lambda: axes.get_area(
                curve,
                x_range=[-1.0 + mu_tracker.get_value(), 1.0 + mu_tracker.get_value()],
                color=[BLUE_C, TEAL_C],
                opacity=0.42,
            )
        )

        formula_box = Text("{formula}", font_size=24, color=YELLOW).to_corner(UR, buff=0.45)

        self.play(Create(axes), Write(axes_labels), run_time=1.2)
        self.play(Create(curve), FadeIn(area), FadeIn(formula_box), run_time=1.4)

        # 3. Narrative Beats (manim-composer)
        beats = [
            {beats_py}
        ]
        caption_mob = None
        for idx, (head, cap) in enumerate(beats):
            new_cap = Text(f"{{head}}: {{cap[:72]}}", font_size=20, color=WHITE).to_edge(DOWN, buff=0.3)
            anims = [ FadeIn(new_cap) ] if caption_mob is None else [ ReplacementTransform(caption_mob, new_cap) ]
            if idx % 2 == 1:
                anims.append(mu_tracker.animate.set_value(0.85))
                anims.append(sigma_tracker.animate.set_value(0.8))
            else:
                anims.append(mu_tracker.animate.set_value(-0.45 * idx))
                anims.append(sigma_tracker.animate.set_value(1.1))
            self.play(*anims, run_time=1.8)
            caption_mob = new_cap
            self.wait(1.0)

        self.play(mu_tracker.animate.set_value(0.0), sigma_tracker.animate.set_value(1.0), run_time=1.2)
        self.wait(1.5)
'''


def build_artifact_html(spec: dict) -> str:
    """Build a self-contained, dependency-free interactive HTML5/SVG/Canvas animation player
    implementing the visual craft rules of wheresryan22/anatomy, adithya-s-k/manim_skill,
    and iart-ai/explainer-video-skills, with built-in PNG, SVG, and WebM video recording."""
    spec_json_escaped = json.dumps(spec).replace("</", "<\\/")
    title_esc = html.escape(spec["title"])
    skill_label = html.escape(spec["skill_meta"]["label"])
    modality_label = html.escape(spec["skill_meta"]["modality_label"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title_esc} — BruinBuddy Illustration</title>
<style>
  :root {{
    --bg: #14181a;
    --panel: #1c2124;
    --card: #22282c;
    --ink: #e8ecea;
    --muted: #9aa5a3;
    --line: #2e373b;
    --accent: #4fb89d;
    --blue: #58C4DD;
    --yellow: #FFFF00;
    --green: #83C167;
    --red: #FC6255;
    --teal: #5CD0B3;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 12px;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    user-select: none;
  }}
  .frame {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 30px rgba(0,0,0,0.35);
  }}
  .head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--line);
    background: rgba(255,255,255,0.02);
    flex-wrap: wrap;
  }}
  .head-title {{
    font-weight: 700;
    font-size: 0.96rem;
    color: var(--ink);
  }}
  .head-sub {{
    font-size: 0.78rem;
    color: var(--muted);
    margin-top: 2px;
  }}
  .readout {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.78rem;
    background: var(--card);
    color: var(--yellow);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 4px 8px;
    white-space: nowrap;
  }}
  .stage-wrap {{
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 10;
    background: #111517;
    overflow: hidden;
  }}
  canvas {{
    width: 100%;
    height: 100%;
    display: block;
  }}
  .caption-bar {{
    padding: 10px 14px;
    background: #171c1f;
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    min-height: 60px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 3px;
  }}
  .beat-tag {{
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--accent);
  }}
  .caption-text {{
    font-size: 0.88rem;
    line-height: 1.4;
    color: var(--ink);
  }}
  .controls {{
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: var(--panel);
  }}
  .transport {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }}
  button {{
    background: var(--card);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 7px;
    padding: 5px 10px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }}
  button:hover {{
    border-color: var(--accent);
  }}
  button.primary {{
    background: var(--accent);
    color: #0b1613;
    border-color: var(--accent);
  }}
  .beats-strip {{
    display: flex;
    gap: 4px;
    flex: 1;
    min-width: 140px;
  }}
  .beat-pill {{
    flex: 1;
    height: 26px;
    padding: 0 6px;
    font-size: 0.74rem;
    border-radius: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .beat-pill.active {{
    background: rgba(79, 184, 157, 0.22);
    border-color: var(--accent);
    color: #fff;
  }}
  .sliders {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 10px;
    padding-top: 4px;
  }}
  .slider-group {{
    display: flex;
    flex-direction: column;
    gap: 3px;
    background: var(--card);
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid var(--line);
  }}
  .slider-head {{
    display: flex;
    justify-content: space-between;
    font-size: 0.76rem;
    color: var(--muted);
  }}
  .slider-val {{
    color: var(--ink);
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-weight: 700;
  }}
  input[type="range"] {{
    width: 100%;
    accent-color: var(--accent);
    cursor: pointer;
  }}
</style>
</head>
<body>
<div class="frame">
  <div class="head">
    <div>
      <div class="head-title" id="fig-title">{title_esc}</div>
      <div class="head-sub">{skill_label} · {modality_label}</div>
    </div>
    <div class="readout" id="live-readout">f(x)</div>
  </div>

  <div class="stage-wrap">
    <canvas id="stage" width="800" height="500"></canvas>
  </div>

  <div class="caption-bar">
    <div class="beat-tag" id="beat-heading">Step 1</div>
    <div class="caption-text" id="beat-caption">Loading animation…</div>
  </div>

  <div class="controls">
    <div class="transport">
      <button class="primary" id="btn-play" type="button">⏸ Pause</button>
      <button id="btn-restart" type="button">↺ Replay</button>
      <div class="beats-strip" id="beats-strip"></div>
    </div>
    <div class="sliders">
      <div class="slider-group">
        <div class="slider-head">
          <span id="lbl-p1">Parameter</span>
          <span class="slider-val" id="val-p1">0.50</span>
        </div>
        <input type="range" id="rng-p1" />
      </div>
      <div class="slider-group">
        <div class="slider-head">
          <span id="lbl-p2">Secondary</span>
          <span class="slider-val" id="val-p2">8</span>
        </div>
        <input type="range" id="rng-p2" />
      </div>
    </div>
  </div>
</div>

<script>
const SPEC = {spec_json_escaped};

const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const btnPlay = document.getElementById('btn-play');
const btnRestart = document.getElementById('btn-restart');
const beatsStrip = document.getElementById('beats-strip');
const beatHeading = document.getElementById('beat-heading');
const beatCaption = document.getElementById('beat-caption');
const liveReadout = document.getElementById('live-readout');

const rngP1 = document.getElementById('rng-p1');
const rngP2 = document.getElementById('rng-p2');
const lblP1 = document.getElementById('lbl-p1');
const lblP2 = document.getElementById('lbl-p2');
const valP1 = document.getElementById('val-p1');
const valP2 = document.getElementById('val-p2');

lblP1.textContent = SPEC.param_label || 'Parameter p';
rngP1.min = SPEC.param_min;
rngP1.max = SPEC.param_max;
rngP1.step = SPEC.param_step;
rngP1.value = SPEC.param_default;

lblP2.textContent = SPEC.secondary_label || 'Scale / N';
rngP2.min = SPEC.secondary_min;
rngP2.max = SPEC.secondary_max;
rngP2.step = SPEC.secondary_step;
rngP2.value = SPEC.secondary_default;

let playing = true;
let beatIdx = 0;
let beatElapsed = 0;
const BEAT_DURATION = 4.2; // seconds per narrative beat
let lastTs = performance.now();
let p1 = parseFloat(rngP1.value);
let p2 = parseFloat(rngP2.value);

// Particles for isometric / Galton / flow animations
const particles = Array.from({{ length: 28 }}, (_, i) => ({{
  phase: (i / 28) * Math.PI * 2,
  row: (i % 7),
  col: ((i * 3) % 7) - 3,
  speed: 0.6 + (i % 5) * 0.12
}}));

function setBeat(idx) {{
  beatIdx = Math.max(0, Math.min(SPEC.beats.length - 1, idx));
  beatElapsed = 0;
  const b = SPEC.beats[beatIdx];
  beatHeading.textContent = `${{b.heading}}  ·  (${{beatIdx + 1}}/${{SPEC.beats.length}})`;
  beatCaption.textContent = b.caption;
  Array.from(beatsStrip.children).forEach((el, i) => {{
    el.classList.toggle('active', i === beatIdx);
  }});
}}

SPEC.beats.forEach((b, i) => {{
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'beat-pill' + (i === 0 ? ' active' : '');
  btn.textContent = `Beat ${{i + 1}}`;
  btn.title = b.heading;
  btn.onclick = () => setBeat(i);
  beatsStrip.appendChild(btn);
}});
setBeat(0);

rngP1.oninput = () => {{
  p1 = parseFloat(rngP1.value);
  valP1.textContent = p1.toFixed(2);
}};
rngP2.oninput = () => {{
  p2 = parseFloat(rngP2.value);
  valP2.textContent = Number.isInteger(p2) ? String(p2) : p2.toFixed(1);
}};
rngP1.oninput();
rngP2.oninput();

btnPlay.onclick = () => {{
  playing = !playing;
  btnPlay.textContent = playing ? '⏸ Pause' : '▶ Play';
}};
btnRestart.onclick = () => {{
  setBeat(0);
  playing = true;
  btnPlay.textContent = '⏸ Pause';
}};

// Isometric projection helper (from wheresryan22/anatomy: ±30 deg ground axes)
function iso(x, y, z, cx, cy, scale) {{
  return {{
    x: cx + (x - y) * 0.866025 * scale,
    y: cy + (x + y) * 0.5 * scale - z * scale
  }};
}}

// Draw a 4-tone shaded isometric prism (Anatomy craft rule)
function drawIsoBox(x, y, z, wx, wy, wz, cx, cy, scale, topCol, leftCol, rightCol) {{
  const p001 = iso(x, y, z + wz, cx, cy, scale);
  const p101 = iso(x + wx, y, z + wz, cx, cy, scale);
  const p111 = iso(x + wx, y + wy, z + wz, cx, cy, scale);
  const p011 = iso(x, y + wy, z + wz, cx, cy, scale);
  const p100 = iso(x + wx, y, z, cx, cy, scale);
  const p110 = iso(x + wx, y + wy, z, cx, cy, scale);
  const p010 = iso(x, y + wy, z, cx, cy, scale);

  // Top face
  ctx.beginPath();
  ctx.moveTo(p001.x, p001.y);
  ctx.lineTo(p101.x, p101.y);
  ctx.lineTo(p111.x, p111.y);
  ctx.lineTo(p011.x, p011.y);
  ctx.closePath();
  ctx.fillStyle = topCol;
  ctx.fill();
  ctx.strokeStyle = '#111517';
  ctx.lineWidth = 1.1;
  ctx.stroke();

  // Left-front face (x + wx)
  ctx.beginPath();
  ctx.moveTo(p101.x, p101.y);
  ctx.lineTo(p111.x, p111.y);
  ctx.lineTo(p110.x, p110.y);
  ctx.lineTo(p100.x, p100.y);
  ctx.closePath();
  ctx.fillStyle = rightCol;
  ctx.fill();
  ctx.stroke();

  // Right-front face (y + wy)
  ctx.beginPath();
  ctx.moveTo(p011.x, p011.y);
  ctx.lineTo(p111.x, p111.y);
  ctx.lineTo(p110.x, p110.y);
  ctx.lineTo(p010.x, p010.y);
  ctx.closePath();
  ctx.fillStyle = leftCol;
  ctx.fill();
  ctx.stroke();
}}

function drawHeaderOverlay(t) {{
  ctx.save();
  ctx.fillStyle = 'rgba(28, 33, 36, 0.85)';
  ctx.strokeStyle = '#2e373b';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(18, 16, 330, 56, 8);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#e8ecea';
  ctx.font = 'bold 14px -apple-system, sans-serif';
  ctx.fillText(SPEC.title.slice(0, 42), 30, 38);

  ctx.fillStyle = '#FFFF00';
  ctx.font = '13px ui-monospace, SFMono-Regular, monospace';
  ctx.fillText(SPEC.formula.slice(0, 44), 30, 58);
  ctx.restore();
}}

// 1. Manim 3B1B Distribution & Integral Engine
function renderManim(t, beatProgress) {{
  const W = canvas.width, H = canvas.height;
  const ox = 90, oy = H - 75, gw = W - 150, gh = H - 165;

  // Subtle 3B1B coordinate grid
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 8; i++) {{
    const x = ox + (gw * i) / 8;
    ctx.beginPath(); ctx.moveTo(x, oy - gh); ctx.lineTo(x, oy); ctx.stroke();
  }}
  for (let j = 0; j <= 5; j++) {{
    const y = oy - (gh * j) / 5;
    ctx.beginPath(); ctx.moveTo(ox, y); ctx.lineTo(ox + gw, y); ctx.stroke();
  }}

  // Axes
  ctx.strokeStyle = '#9aa5a3';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(ox, oy - gh);
  ctx.lineTo(ox, oy);
  ctx.lineTo(ox + gw, oy);
  ctx.stroke();

  const normP = (p1 - SPEC.param_min) / Math.max(0.001, SPEC.param_max - SPEC.param_min);
  const mu = (normP - 0.5) * 2.4;
  const sigma = 0.55 + (1 - (p2 - SPEC.secondary_min) / Math.max(1, SPEC.secondary_max - SPEC.secondary_min)) * 0.9;

  const pdf = (x) => (1 / (sigma * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((x - mu) / sigma, 2));
  const yMax = 0.85;

  if (SPEC.template === 'bayes_square') {{
    // 3B1B Geometric Bayes unit square
    const sqSize = Math.min(gw * 0.52, gh * 0.88);
    const sx = ox + 60, sy = oy - sqSize - 10;
    const priorW = sqSize * Math.max(0.08, Math.min(0.92, normP));
    const sensH = sqSize * 0.78;
    const falsePosH = sqSize * 0.22;

    // Prior P(H) region (Blue)
    ctx.fillStyle = 'rgba(88, 196, 221, 0.25)';
    ctx.fillRect(sx, sy, priorW, sqSize);
    ctx.fillStyle = 'rgba(131, 193, 103, 0.68)';
    ctx.fillRect(sx, sy + (sqSize - sensH), priorW, sensH);

    // Complement ~H region
    ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.fillRect(sx + priorW, sy, sqSize - priorW, sqSize);
    ctx.fillStyle = 'rgba(252, 98, 85, 0.55)';
    ctx.fillRect(sx + priorW, sy + (sqSize - falsePosH), sqSize - priorW, falsePosH);

    ctx.strokeStyle = '#e8ecea';
    ctx.lineWidth = 2;
    ctx.strokeRect(sx, sy, sqSize, sqSize);
    ctx.beginPath();
    ctx.moveTo(sx + priorW, sy);
    ctx.lineTo(sx + priorW, sy + sqSize);
    ctx.stroke();

    const pTruePos = normP * 0.78;
    const pFalsePos = (1 - normP) * 0.22;
    const post = pTruePos / Math.max(0.0001, pTruePos + pFalsePos);
    liveReadout.textContent = `Posterior P(H|E) = ${{(post * 100).toFixed(1)}}%`;

    // Posterior bar on the right
    const bx = sx + sqSize + 75;
    ctx.fillStyle = '#22282c';
    ctx.fillRect(bx, sy, 54, sqSize);
    ctx.fillStyle = '#83C167';
    ctx.fillRect(bx, sy + sqSize * (1 - post), 54, sqSize * post);
    ctx.strokeStyle = '#58C4DD';
    ctx.strokeRect(bx, sy, 54, sqSize);

    ctx.fillStyle = '#e8ecea';
    ctx.font = 'bold 13px sans-serif';
    ctx.fillText(`P(H) = ${{normP.toFixed(2)}}`, sx + priorW / 2 - 34, sy + sqSize + 24);
    ctx.fillText(`Posterior`, bx - 4, sy - 10);
    return;
  }}

  // Shaded integral area under curve
  const boundRight = -1.2 + (beatIdx + 1) * 0.85 + Math.sin(t * 1.4) * 0.25;
  ctx.beginPath();
  const steps = 120;
  let areaSum = 0;
  for (let i = 0; i <= steps; i++) {{
    const xVal = -3.5 + (7.0 * i) / steps;
    const px = ox + (gw * i) / steps;
    const yVal = pdf(xVal);
    const py = oy - (yVal / yMax) * gh;
    if (xVal <= boundRight) {{
      if (i === 0) ctx.moveTo(px, oy);
      ctx.lineTo(px, py);
      areaSum += yVal * (7.0 / steps);
    }}
  }}
  const lastPx = ox + gw * Math.min(1, Math.max(0, (boundRight + 3.5) / 7.0));
  ctx.lineTo(lastPx, oy);
  ctx.lineTo(ox, oy);
  ctx.closePath();
  const grad = ctx.createLinearGradient(ox, oy - gh, ox, oy);
  grad.addColorStop(0, 'rgba(88, 196, 221, 0.55)');
  grad.addColorStop(1, 'rgba(92, 208, 179, 0.12)');
  ctx.fillStyle = grad;
  ctx.fill();

  // Discrete Riemann / Binomial bars (controlled by secondary slider N)
  const nBars = Math.max(4, Math.min(24, Math.round(p2)));
  for (let b = 0; b < nBars; b++) {{
    const xVal = -3.2 + (6.4 * (b + 0.5)) / nBars;
    const yVal = pdf(xVal);
    const bw = (gw * 0.82) / nBars;
    const bx = ox + ((xVal + 3.5) / 7.0) * gw - bw / 2;
    const bh = (yVal / yMax) * gh;
    ctx.fillStyle = 'rgba(255, 255, 0, 0.14)';
    ctx.strokeStyle = 'rgba(255, 255, 0, 0.45)';
    ctx.lineWidth = 1;
    ctx.fillRect(bx, oy - bh, bw, bh);
    ctx.strokeRect(bx, oy - bh, bw, bh);
  }}

  // Main 3B1B Curve (BLUE_C)
  ctx.beginPath();
  for (let i = 0; i <= steps; i++) {{
    const xVal = -3.5 + (7.0 * i) / steps;
    const px = ox + (gw * i) / steps;
    const py = oy - (pdf(xVal) / yMax) * gh;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }}
  ctx.strokeStyle = '#58C4DD';
  ctx.lineWidth = 3.5;
  ctx.stroke();

  // Moving tracker dot on curve
  const trackerPx = ox + ((mu + 3.5) / 7.0) * gw;
  const trackerPy = oy - (pdf(mu) / yMax) * gh;
  ctx.fillStyle = '#FFFF00';
  ctx.beginPath();
  ctx.arc(trackerPx, trackerPy, 6, 0, Math.PI * 2);
  ctx.fill();

  liveReadout.textContent = `μ=${{mu.toFixed(2)}} · σ=${{sigma.toFixed(2)}} · ∫=${{Math.min(1, areaSum).toFixed(3)}}`;
}}

// 2. Anatomy Isometric Apparatus Engine (wheresryan22/anatomy)
function renderAnatomyIsometric(t) {{
  const W = canvas.width, H = canvas.height;
  const cx = W * 0.5, cy = H * 0.62, scale = 24;
  const normP = (p1 - SPEC.param_min) / Math.max(0.001, SPEC.param_max - SPEC.param_min);
  const bins = 7;

  // Base instrument bench plate (4-tone shaded isometric solid)
  drawIsoBox(-5.5, -4.5, -0.6, 11, 9, 0.6, cx, cy, scale, '#2a3236', '#1e2428', '#161b1e');

  // Backboard / hopper frame
  drawIsoBox(-4.8, -4.2, 0, 0.6, 8.4, 5.2, cx, cy, scale, '#384349', '#2b3439', '#20272b');

  // Peg array in isometric space
  for (let r = 0; r < 5; r++) {{
    for (let c = -r; c <= r; c += 2) {{
      const px = -2.8 + r * 1.1;
      const py = c * 0.65;
      const pz = 4.2 - r * 0.65;
      const pt = iso(px, py, pz, cx, cy, scale);
      ctx.fillStyle = '#FFFF00';
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 4.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#111517';
      ctx.lineWidth = 1;
      ctx.stroke();
    }}
  }}

  // Collector accumulator bars (Binomial distribution heights driven by live model p1)
  const nTrials = bins - 1;
  const fact = (n) => (n <= 1 ? 1 : n * fact(n - 1));
  for (let k = 0; k < bins; k++) {{
    const comb = fact(nTrials) / (fact(k) * fact(nTrials - k));
    const prob = comb * Math.pow(normP, k) * Math.pow(1 - normP, nTrials - k);
    const barH = Math.max(0.25, prob * 8.5);
    const by = (k - 3) * 1.05 - 0.35;
    const isPeak = Math.abs(k - normP * nTrials) < 0.85;
    drawIsoBox(
      2.4, by, 0,
      1.5, 0.72, barH,
      cx, cy, scale,
      isPeak ? '#67e0c2' : '#58C4DD',
      isPeak ? '#4fb89d' : '#3d93a8',
      isPeak ? '#358570' : '#2b6a7a'
    );
  }}

  // Live animated particles falling through the apparatus
  const activeCount = Math.max(4, Math.min(28, Math.round(p2 * 1.6)));
  for (let i = 0; i < activeCount; i++) {{
    const pt = particles[i];
    const prog = ((t * pt.speed + pt.phase) % (Math.PI * 2)) / (Math.PI * 2);
    const px = -3.2 + prog * 5.6;
    const drift = (normP - 0.5) * 3.2 * prog + Math.sin(prog * 12 + i) * 0.45;
    const pz = 4.6 * (1 - prog * 0.82);
    const screen = iso(px, drift, pz, cx, cy, scale);
    ctx.fillStyle = i % 3 === 0 ? '#FFFF00' : '#FC6255';
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, 4.5, 0, Math.PI * 2);
    ctx.fill();
  }}

  liveReadout.textContent = `Apparatus Model · Bias p=${{normP.toFixed(2)}} · E[Bin]=${{(normP * nTrials).toFixed(2)}}`;
}}

// 3. Diagram & Whiteboard Explainer Engine (iart-ai/explainer-video-skills)
function renderExplainerDiagram(t, beatProgress) {{
  const W = canvas.width, H = canvas.height;
  const nodes = SPEC.nodes;
  const count = nodes.length;
  const spacing = (W - 140) / Math.max(1, count);
  const cy = H * 0.52;
  const isWhiteboard = SPEC.skill === 'explainer_storyboard';

  // Draw progressive connectors (nodes -> edges -> labels)
  for (let i = 0; i < count - 1; i++) {{
    const x1 = 70 + spacing * i + 58;
    const x2 = 70 + spacing * (i + 1) - 58;
    const revealed = i <= beatIdx;

    ctx.save();
    ctx.strokeStyle = revealed ? '#4fb89d' : 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 3;
    if (revealed) {{
      ctx.setLineDash([8, 6]);
      ctx.lineDashOffset = -t * 28;
    }}
    ctx.beginPath();
    ctx.moveTo(x1, cy);
    ctx.lineTo(x2, cy);
    ctx.stroke();
    ctx.restore();

    // Traveling signal packet on active edge
    if (revealed) {{
      const pktX = x1 + ((t * 0.75 + i * 0.3) % 1) * (x2 - x1);
      ctx.fillStyle = '#FFFF00';
      ctx.beginPath();
      ctx.arc(pktX, cy, 5, 0, Math.PI * 2);
      ctx.fill();
    }}
  }}

  // Draw progressive nodes with focus dimming
  nodes.forEach((n, i) => {{
    const nx = 70 + spacing * i;
    const isActive = i === beatIdx % count;
    const isPast = i < beatIdx % count;
    const alpha = isActive ? 1.0 : (isPast ? 0.82 : 0.28);

    ctx.save();
    ctx.globalAlpha = alpha;
    const boxW = 118, boxH = 86;
    const lift = isActive ? -6 : 0;

    ctx.fillStyle = isActive ? '#263238' : '#1c2124';
    ctx.strokeStyle = isActive ? n.color : '#2e373b';
    ctx.lineWidth = isActive ? 3 : 1.5;
    ctx.beginPath();
    ctx.roundRect(nx - boxW / 2, cy - boxH / 2 + lift, boxW, boxH, 12);
    ctx.fill();
    ctx.stroke();

    // Step badge
    ctx.fillStyle = n.color;
    ctx.font = 'bold 12px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`STAGE ${{i + 1}}`, nx, cy - 16 + lift);

    ctx.fillStyle = '#e8ecea';
    ctx.font = 'bold 13px -apple-system, sans-serif';
    ctx.fillText(n.label.slice(0, 16), nx, cy + 5 + lift);

    ctx.fillStyle = '#9aa5a3';
    ctx.font = '11px -apple-system, sans-serif';
    ctx.fillText((n.sub || '').slice(0, 20), nx, cy + 24 + lift);

    // Whiteboard marker nib tracking active box perimeter
    if (isWhiteboard && isActive) {{
      const angle = (t * 2.5) % (Math.PI * 2);
      const nibX = nx + Math.cos(angle) * (boxW * 0.45);
      const nibY = cy + lift + Math.sin(angle) * (boxH * 0.45);
      ctx.fillStyle = '#FFFF00';
      ctx.beginPath();
      ctx.moveTo(nibX, nibY);
      ctx.lineTo(nibX + 12, nibY - 18);
      ctx.lineTo(nibX + 4, nibY - 22);
      ctx.closePath();
      ctx.fill();
    }}
    ctx.restore();
  }});

  // Bottom progress bar synced to VO timing (~2.3 words/sec)
  const barW = W - 140;
  const overall = (beatIdx + Math.min(1, beatProgress)) / Math.max(1, SPEC.beats.length);
  ctx.fillStyle = '#22282c';
  ctx.fillRect(70, H - 36, barW, 8);
  ctx.fillStyle = '#4fb89d';
  ctx.fillRect(70, H - 36, barW * overall, 8);

  liveReadout.textContent = `Beat ${{beatIdx + 1}}/${{SPEC.beats.length}} · ${{SPEC.beats[beatIdx]?.highlight || ''}}`;
}}

function frame(now) {{
  const dt = Math.min(0.1, (now - lastTs) / 1000);
  lastTs = now;
  if (playing) {{
    beatElapsed += dt;
    if (beatElapsed >= BEAT_DURATION) {{
      setBeat((beatIdx + 1) % SPEC.beats.length);
    }}
  }}
  const t = now / 1000;
  const beatProgress = beatElapsed / BEAT_DURATION;

  ctx.fillStyle = '#111517';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (SPEC.skill === 'anatomy_isometric' || SPEC.template === 'clt_galton' || SPEC.template === 'isometric_rig') {{
    renderAnatomyIsometric(t);
  }} else if (SPEC.skill === 'explainer_diagram' || SPEC.skill === 'explainer_storyboard' || SPEC.template === 'flow_diagram' || SPEC.template === 'whiteboard_story') {{
    renderExplainerDiagram(t, beatProgress);
  }} else {{
    renderManim(t, beatProgress);
  }}

  drawHeaderOverlay(t);
  requestAnimationFrame(frame);
}}
requestAnimationFrame(frame);

// Parent window bridge for PNG and WebM Video export
window.addEventListener('message', async (ev) => {{
  if (!ev.data || !ev.data.type) return;
  if (ev.data.type === 'bb_export_png') {{
    const dataUrl = canvas.toDataURL('image/png');
    window.parent.postMessage({{ type: 'bb_export_result', format: 'png', url: dataUrl }}, '*');
  }} else if (ev.data.type === 'bb_export_webm') {{
    try {{
      const stream = canvas.captureStream(30);
      const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
        ? 'video/webm;codecs=vp9'
        : 'video/webm';
      const rec = new MediaRecorder(stream, {{ mimeType: mime }});
      const chunks = [];
      rec.ondataavailable = (e) => {{ if (e.data && e.data.size > 0) chunks.push(e.data); }};
      rec.onstop = () => {{
        const blob = new Blob(chunks, {{ type: 'video/webm' }});
        const reader = new FileReader();
        reader.onloadend = () => {{
          window.parent.postMessage({{ type: 'bb_export_result', format: 'webm', url: reader.result }}, '*');
        }};
        reader.readAsDataURL(blob);
      }};
      setBeat(0);
      playing = true;
      rec.start();
      setTimeout(() => {{ if (rec.state === 'recording') rec.stop(); }}, 4500);
    }} catch (err) {{
      window.parent.postMessage({{ type: 'bb_export_error', message: String(err) }}, '*');
    }}
  }}
}});
</script>
</body>
</html>"""


def build_svg_snapshot(spec: dict) -> str:
    """Generate a clean downloadable vector SVG diagram summarizing the illustration and its beats."""
    title = html.escape(spec["title"])
    subtitle = html.escape(spec["subtitle"])
    formula = html.escape(spec["formula"])
    skill_label = html.escape(spec["skill_meta"]["label"])
    beats_svg = []
    for i, b in enumerate(spec["beats"][:4]):
        y = 140 + i * 72
        h_text = html.escape(b["heading"])
        c_text = html.escape(b["caption"][:95])
        beats_svg.append(
            f'<rect x="40" y="{y}" width="720" height="58" rx="10" fill="#1c2124" stroke="#2e373b"/>'
            f'<text x="60" y="{y + 24}" fill="#4fb89d" font-family="sans-serif" font-size="13" font-weight="bold">{h_text}</text>'
            f'<text x="60" y="{y + 44}" fill="#e8ecea" font-family="sans-serif" font-size="12">{c_text}</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 460" width="800" height="460">'
        '<rect width="800" height="460" fill="#14181a"/>'
        f'<text x="40" y="48" fill="#e8ecea" font-family="sans-serif" font-size="22" font-weight="bold">{title}</text>'
        f'<text x="40" y="74" fill="#9aa5a3" font-family="sans-serif" font-size="14">{subtitle} ({skill_label})</text>'
        f'<text x="40" y="106" fill="#FFFF00" font-family="monospace" font-size="15">{formula}</text>'
        + "".join(beats_svg)
        + "</svg>"
    )


def _sanitize_spec_on_leak(concept: str, skill: str, pset_title: str) -> dict:
    """Fallback general conceptual spec if the guard detects any solution overlap on a Graded problem set."""
    return _normalize_spec(
        {
            "title": f"Concept Intuition: {concept[:48]}",
            "subtitle": f"General conceptual walkthrough for {pset_title} (using synthetic values)",
            "formula": "General Method & Intuition",
            "beats": [
                {
                    "step": 1,
                    "heading": "1. Identify What Is Given",
                    "caption": "Start from the definitions in the lecture notes and list the known parameters with synthetic test values.",
                    "highlight": "Definitions",
                },
                {
                    "step": 2,
                    "heading": "2. Map the Relationship",
                    "caption": "Observe how changing the input parameter shifts the distribution or state transition in general.",
                    "highlight": "Structure",
                },
                {
                    "step": 3,
                    "heading": "3. Check Boundary Cases",
                    "caption": "Test extreme values (such as p near 0 or 1) using the slider to build intuition before solving your problem.",
                    "highlight": "Bounds",
                },
            ],
        },
        skill,
        concept,
        f"Concept Intuition: {concept[:48]}",
    )


def generate_illustration(
    kb: CourseKnowledge,
    course: dict,
    chat: dict,
    user_id: int,
    message_id: int | None = None,
    prompt: str | None = None,
    preferred_skill: str = "auto",
) -> dict:
    """Route the chat concept to one of the 3 visual skill packs, check leak guards, and persist the illustration."""
    course_id, chat_id = course["id"], chat["id"]
    attr = {"course_id": course_id, "user_id": user_id, "chat_id": chat_id}

    with db() as conn:
        if message_id:
            rows = conn.execute(
                "SELECT id, role, content FROM messages WHERE chat_id=? AND id<=? ORDER BY id DESC LIMIT 6",
                (chat_id, message_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 6",
                (chat_id,),
            ).fetchall()
    history = [{"id": r["id"], "role": r["role"], "content": r["content"]} for r in reversed(rows)]
    target_msg_id = message_id or (history[-1]["id"] if history else None)

    user_msgs = [m["content"] for m in history if m["role"] == "user"]
    latest_text = (prompt or "").strip() or (user_msgs[-1] if user_msgs else chat["title"])
    convo_excerpt = "\n".join(f"{m['role'].upper()}: {m['content'][:500]}" for m in history[-4:]) or latest_text

    # Determine problem set mode (strictest mode wins; solutions stay protected)
    attached = chat["doc_id"] if chat["kind"] == "pset" else None
    problem_doc = kb.turn_pset(latest_text, user_msgs[:-1], attached)
    rule = kb.rule(problem_doc)
    mode = rule["mode"] if rule else None

    # Retrieve only student-visible (public) course chunks
    chunks = _retrieve(kb, chat, latest_text, problem_doc, " ".join(user_msgs[-2:]))
    materials_text = "\n\n".join(f"[S{i}] {c.title}, p. {c.page}\n{c.text[:450]}" for i, c in enumerate(chunks, start=1))

    # Stage 1: Route to the right skill
    if preferred_skill in SKILLS:
        skill = preferred_skill
        concept = (prompt or latest_text).strip().replace("\n", " ")[:60] or chat["title"]
        title = f"Visualizing {concept[:50]}"
        rationale = f"Selected {SKILL_META[skill]['label']} ({SKILL_META[skill]['modality_label']}) as requested."
    else:
        route_raw = llm.complete(
            "illustrate_route",
            [
                {"role": "system", "content": ROUTE_SYSTEM},
                {
                    "role": "user",
                    "content": f"CONVERSATION:\n{convo_excerpt}\n\nFOCUS REQUEST: {prompt or '(illustrate the main concept)'}\n\n"
                    f"COURSE MATERIALS:\n{materials_text or '(none)'}",
                },
            ],
            max_tokens=300,
            attr=attr,
        )
        route = llm.parse_json(route_raw)
        skill = route.get("skill") if route.get("skill") in SKILLS else heuristic_skill(f"{latest_text} {convo_excerpt}")
        concept = str(route.get("concept") or latest_text[:60]).strip()[:60]
        title = str(route.get("title") or f"Visualizing {concept}").strip()[:70]
        rationale = str(
            route.get("rationale")
            or f"Chose {SKILL_META[skill]['label']} to turn {concept} into an interactive {SKILL_META[skill]['modality_label'].lower()}."
        ).strip()[:220]

    # Stage 2: Generate the visual animation specification
    graded_note = GRADED_NOTE.format(pset_title=rule["title"]) if mode == "graded" and rule else ""
    gen_raw = llm.complete(
        "illustrate_gen",
        [
            {
                "role": "system",
                "content": GEN_SYSTEM.format(
                    skill=skill,
                    skill_label=SKILL_META[skill]["label"],
                    graded_note=graded_note,
                ),
            },
            {
                "role": "user",
                "content": f"CONCEPT: {concept}\nTITLE: {title}\nCONVERSATION:\n{convo_excerpt}\n\n"
                f"COURSE MATERIALS:\n{materials_text or '(none)'}",
            },
        ],
        max_tokens=1100,
        attr=attr,
    )
    raw_spec = llm.parse_json(gen_raw)
    spec = _normalize_spec(raw_spec, skill, concept, title)

    # Academic Integrity Guard: check for solution leakage on Graded problem sets
    combined_text = " ".join(
        [
            spec["title"],
            spec["subtitle"],
            spec["formula"],
            *(f"{b['heading']} {b['caption']} {b['highlight']}" for b in spec["beats"]),
            *(f"{n['label']} {n['sub']}" for n in spec["nodes"]),
        ]
    )
    leaked = kb.guard.leaks(combined_text)
    if not leaked and mode == "graded" and problem_doc:
        sol_chunks = solution_chunks_for(problem_doc, latest_text + " " + " ".join(user_msgs[-2:]))
        if sol_chunks:
            leaked = _llm_leak(sol_chunks, combined_text, attr)
    if leaked:
        spec = _sanitize_spec_on_leak(concept, skill, rule["title"] if rule else "this problem set")

    artifact_html = build_artifact_html(spec)
    manim_code = build_manim_code(spec)
    modality = SKILL_META[skill]["modality"]

    with db() as conn:
        ill_id = conn.execute(
            "INSERT INTO illustrations(chat_id,message_id,course_id,user_id,concept,skill,modality,title,rationale,"
            "spec_json,artifact_html,manim_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
            (
                chat_id,
                target_msg_id,
                course_id,
                user_id,
                concept,
                skill,
                modality,
                spec["title"],
                rationale,
                json.dumps(spec),
                artifact_html,
                manim_code,
                now(),
            ),
        ).fetchone()["id"]

    return {
        "id": ill_id,
        "chat_id": chat_id,
        "message_id": target_msg_id,
        "concept": concept,
        "skill": skill,
        "skill_meta": SKILL_META[skill],
        "modality": modality,
        "title": spec["title"],
        "rationale": rationale,
        "spec": spec,
        "artifact_html": artifact_html,
        "manim_code": manim_code,
    }
