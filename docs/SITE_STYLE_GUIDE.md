# Public Site Style Guide

Governs `docs/index.html` (landing page) and `docs/tdd.html` (technical design doc), served via GitHub Pages. Read this before editing either file, and update it when a genuinely new pattern gets introduced — this is a living reference, unlike `docs/notes/DESIGN.md`'s point-in-time-snapshot rule.

---

## Palette

Both pages share one token set. **A token with the same name must mean the same thing in both files** — this was violated once already (`--amber` was a green selection-highlight color in `index.html` but a real warning-amber in `tdd.html`) and had to be untangled into `--amber` (warning/boundary, `#8a5a17`) vs `--select-hl` (selection highlight, `#047857`), kept as separate tokens. Don't reintroduce that collision.

```
--paper: #fafaf9        --paper-raised: #ffffff
--ink: #171f1d          --ink-soft: #3b453f       --ink-faint: #5a635d
--teal: #20464c          --teal-bright: #2f626a
--amber: #8a5a17         --select-hl: #047857
--line: #cdccbf          --focus: #047857          --code-bg: #e6e4d8
```

**`--paper` changed from a warm cream (`#efeee6`) to a near-white (`#fafaf9`)** so the same token set could become the single canonical brand palette shared with the actual running app (Tailwind `@theme` in `frontend/src/index.css`), not just the docs/marketing pages. Cream read well for this page's editorial/long-form register, but a functional data-dense app (forms, tables, medical values) benefits from a neutral background, and warm-on-warm made `--amber` feel less distinct even though it never actually failed contrast (verified: `--amber` on old paper 5.07:1, on new paper 5.66:1 — both pass AA regardless). `--paper-raised` moved from `#f7f6ef` to pure white to preserve the "raised = lighter than base" relationship now that base itself is near-white.

tdd.html-only semantic tokens: `--tag-bg`, `--risk-bg`, `--gap-bg`, `--gap-ink` (`#9a3a2e`, a distinct rust tone for "known gaps," separate from the amber used for "risks").

**Semantic meaning is fixed — don't reuse a color for something new without renaming it:**
- **Teal** = runs locally / local AI call (Ollama)
- **Amber** = crosses the anonymization/external trust boundary, or a "risk" callout
- **Gap-ink (rust)** = "known gap" callout, visually distinct from amber-risk so the two categories don't blur
- **Ink-faint** = neutral labels/captions, no semantic weight

**Both `--ink-faint` and `--amber` have already failed WCAG AA (4.5:1) as text once** — `--ink-faint` was `#6b746e` (4.15:1), `--amber` was `#b5761f` (3.24:1). Any time a token's value changes, recompute contrast against `--paper` before shipping (see Accessibility section for the formula). Don't eyeball it.

Both pages are deliberately **single-theme** (light/paper), not dark-mode adaptive — `index.html`'s redaction-bar hero animation needs dark ink on light paper to read, and `tdd.html` matches it for continuity. If a future page in this family has no such constraint, dark-mode support is worth adding properly (tokens + `@media (prefers-color-scheme: dark)` + `:root[data-theme]` overrides), but don't do it half-way.

## Typography

- **Headings, labels, eyebrows, code**: `ui-monospace, "SF Mono", Menlo, Consolas, "Roboto Mono", monospace` — carries the "patient chart" motif from the brand identity.
- **Body prose**: `Iowan Old Style, Charter, Georgia, "Noto Serif", serif`.
- Base body size: 17px (`index.html`) / 16.5px (`tdd.html`, deliberately slightly denser since it's a reference doc, not a landing page).
- **Line length**: every prose paragraph and list caps at **80ch** (at the 16.5-17px base size). Not justified — browser justification stretches word-spacing unevenly (no real hyphenation engine) and WCAG 2.1 SC 1.4.8 explicitly lists "not justified" as a requirement, same criterion behind the line-length cap itself.

### The `ch`-compensation rule (read this before adding any small text)

`ch` is relative to **the element's own font-size**, not the page's base size. A paragraph at 13px with `max-width: 80ch` renders visibly narrower than one at 16.5px with the same `80ch` — this bug shipped multiple times in this codebase before being caught. Any element with a font-size smaller than the base 16.5px needs its own compensated value:

```
target_ch = 80 × (16.5 / element_font_size_px)
```

Worked values already in use — reuse these rather than recomputing if you're adding another element at one of these exact sizes:

| Font size | Compensated max-width |
|-----------|------------------------|
| 13px      | 102ch                  |
| 13.5px    | 98ch                   |
| 14px      | 94ch                   |
| 14.5px    | 91ch                   |
| 16.5px (base) | 80ch               |

Applies to: any `<p>`, `<dd>`, or similar prose element with an inline or class-based `font-size` override. Check `footer.doc-footer p`, `.panel > .dek`, `.chart-line p`, `.boundary p`, `.accordion-item .body p`, `.gterm dd`, `.faq-item .a` for the pattern if you need a template.

### Don't nest a narrower cap inside an already-narrow container

A second, historically shipped bug: setting an explicit `max-width` on text sitting inside a grid/flex column that's *already* narrower than that cap does nothing useful and just looks like a rendering bug (text stops short, leaving dead space before the row's border/divider ends). Either let the text fill its actual container, or explicitly compute the cap relative to the container's real available width — never guess a flat ch value without checking what it's nested inside.

## Layout

- `tdd.html`'s `.panel` content column is 820px, **centered** (`margin: 0 auto`), not left-aligned against the sidebar. Centering was the fix for "content stuck to the left half, dead space on the right" — don't revert to left-alignment without also solving that.
- **Breaking a wide element (e.g. a diagram) out of the 820px reading column**: prose should stay at 80ch/94ch/etc. regardless of container width, so don't widen `.panel` itself — instead give the wide element its own breakout wrapper:

  ```css
  .arch-wide {
    width: clamp(700px, calc(100vw - 420px), 950px); /* NOT width:100% + max-width */
    margin-left: 50%;
    transform: translateX(-50%);
  }
  ```

  **Pitfall already hit once**: `width: 100%; max-width: clamp(...)` does *not* achieve a breakout — `width: 100%` resolves to a definite value (the containing block's width) before `max-width` is ever evaluated, and `max-width` only caps a value *downward*, it never stretches one. The `width` property itself must be the clamp expression.
- Sidebar-nav + tabbed panels (not one long scroll) is the pattern for `tdd.html`'s 8 sections — reference/technical docs benefit from jump-to-section navigation; a single-scroll landing page (`index.html`) does not need this.

## System architecture diagrams

Hand-built HTML/CSS/inline-SVG — not mermaid. Rationale: full control over brand alignment (icon style, palette) and per-node semantic differentiation that generic diagram tools don't give you.

- **Icons, not just color, differentiate node types.** A set of ~16×16 viewBox, single-stroke (`stroke-width` ~1.2-1.3, `stroke="currentColor"`) line-art icons already exists for: file, chip (local model), checkmark, database (cylinder), gear (process), lock (boundary), API (brackets), browser, cloud (external). Defined once as `<symbol>` inside a hidden `<svg>` (`position:absolute;width:0;height:0;overflow:hidden`), referenced via `<use href="#icon-x">`. Add new icons to that same `<defs>` block in the same style rather than reaching for an emoji or an external icon font.
- **Every decorative icon `<svg>` needs `aria-hidden="true"`.** Without it, screen readers announce an unlabeled "graphic" before every single node's text label — shipped as a real bug across 18 icons before being caught.
- **Grouping boxes (dashed boundary containers), not per-node color alone, are what make a diagram read as "architecture."** Mirrors the AWS-diagram convention of nested Region/VPC/AZ boxes. If there's a real trust boundary or logical grouping, give it an actual bordered container.
- **Border-weight hierarchy communicates nesting**, not background-color fills: outer boundary = dashed + color (teal); phase/stage containers = solid, darker, thicker neutral (`var(--ink-soft)`, 1.5px); individual nodes = solid, lighter, thinner neutral (`var(--line)`, 1px). A background-tint-per-section was tried and reverted — it competed with the semantic color system (teal/amber already mean something) for no informational gain.
- **Boundaries can nest.** `.arch-boundary`/`.arch-boundary-label` isn't limited to one outer "trust boundary" per diagram — a second `.arch-boundary` can wrap a sub-grouping of phases *inside* an outer boundary when several consecutive phases are really stages of one named pipeline (e.g. `tdd.html`'s "4-stage context selection pipeline" boundary, nested inside the outer "your machine" boundary, wrapping just the Select and Anonymize phases). Use `icon-gear` for a pipeline-grouping label, reserving `icon-lock` for boundaries that are actually about a privacy/trust crossing.
- **Small pill chips (`.arch-tool`) for an enumerable set of sub-items under one node** — e.g. listing which tools an agentic loop can call. `.arch-tool` (solid `var(--teal-bright)` border) marks an item that's actually built/available; `.arch-tool--roadmap` (dashed `var(--ink-faint)` border) marks a proposed-but-not-built candidate — same solid-vs-dashed "is this real yet" convention as everywhere else in these diagrams, just applied at pill scale instead of node/boundary scale. Group built vs. roadmap into separate `.arch-tools-row`s with a small `.arch-tools-label` prefix (e.g. "available" / "roadmap") rather than mixing them in one row — and add a legend entry so the solid/dashed distinction doesn't rely on the reader inferring it.
- **Keep semantic color scarce.** Don't add a new color "just to differentiate a section" — that dilutes the one or two colors that actually carry meaning. Use border weight, bold/weight typography, or neutral-tone variation instead.
- **Vertical stack of full-width phase boxes beats horizontal lanes with inter-card arrows.** The horizontal-lanes version reliably produced "dangling arrow" bugs: `flex-wrap` would wrap a card to a new line while the arrow pointing at it stayed on the line above, pointing at nothing. A vertical spine of full-width boxes, each containing its own horizontal row of sub-nodes, guarantees every vertical arrow always has something directly below it regardless of viewport width.
- **A branch/exception in the flow** (e.g., "may optionally call out to an external service") reads better as a separate side element with a labeled bidirectional arrow and full explanatory text, not folded into the main sequential spine as an inline either/or choice.
- **Shrinking a whole diagram**: use `zoom`, not `transform: scale()`, for the final implementation — `zoom` triggers real layout reflow (no leftover reserved blank space), while `transform: scale()` leaves the original untransformed box size reserved in the flow. `transform: scale()` is fine for a quick visual preview during iteration, but swap to `zoom` once a size is settled. Always keep the smallest text at or above the accessibility floor (**10.5px**, see below) regardless of scale factor.
- **Never let a diagram force a horizontal scrollbar as the fix for overflow.** Use `flex-wrap: wrap` (same font size, content reflows) instead.

## Status/strategy badges

Small inline `<span>` badges (e.g. `.strat-tag` on `tdd.html`, used to mark a pipeline stage as deterministic/llm/hybrid) follow the same "keep semantic color scarce" rule as diagrams — reuse existing tokens, don't introduce a new color per badge variant:

- Neutral/default variant: `var(--ink-faint)` text, `var(--line)` border.
- "Local AI call" variant: `var(--teal-bright)` text and border — same meaning as teal everywhere else on the page.
- "Mixed/hybrid" variant: `var(--teal-bright)` border but **dashed** instead of solid, `var(--ink-soft)` text — border *style*, not a new color, carries the "partial/conditional" meaning.

## Deep Dives: group by system-design phase, not insertion order

`tdd.html`'s Deep Dives accordion is grouped under `.dd-group-label` headers that mirror the phase names used in the System Design diagram's vertical stack (Ingest → Select → Anonymize → Orchestrate → Backend → Serve), so a reader can trace "the box I'm looking at in the diagram" straight to "the accordion section that explains it," rather than a flat list in whatever order sections were written.

- Not every deep dive maps to a pipeline phase. Ones that don't (e.g. data model/schema, a cross-cutting feature like nudging) go in a trailing **Cross-cutting** group rather than being force-fit into a phase they don't belong to, or silently dropped from grouping.
- `.dd-group-label` reuses the sidebar nav's existing group-label typography (`ui-monospace`, 11px, uppercase, `letter-spacing: 0.08em`, `var(--ink-faint)`) rather than introducing a new heading style — the same "this is a grouping label, not new heading hierarchy" visual role in both places.
- When a phase's diagram box covers ground handled by more than one deep dive (e.g. "Orchestrate" spans both the agentic tool-use loop and specialty-aware prompting), put both accordion items under that one group rather than splitting the group further — the diagram phase is the grouping unit, not a 1:1 mapping to accordion items.

## Accessibility checklist

Apply this to any new page or component in this family, not just re-fixing things already caught here:

- [ ] **Contrast**: compute WCAG AA (4.5:1 normal text) for every new/changed color-as-text combination — don't eyeball it. Quick Python check:
  ```python
  def lum(hex_):
      r,g,b = [int(hex_.lstrip('#')[i:i+2],16)/255 for i in (0,2,4)]
      f = lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
      r,g,b = f(r),f(g),f(b)
      return 0.2126*r+0.7152*g+0.0722*b
  def ratio(a,b):
      la,lb = sorted([lum(a),lum(b)], reverse=True)
      return (la+0.05)/(lb+0.05)
  ```
- [ ] **Minimum legible text size**: 10.5px floor for the smallest supplementary/sub-label text anywhere on the page. Established after `.arch-sub` shipped at 9.5px.
- [ ] **Skip-to-content link** at the very top of `<body>`, visually hidden until `:focus` (see `.skip-link` in either file for the pattern) — required on every page, not optional polish.
- [ ] **Decorative icons**: `aria-hidden="true"` on the `<svg>`.
- [ ] **Custom tab/accordion widgets need real ARIA**, not just visual styling: `role="tablist"/"tab"/"tabpanel"`, `aria-selected`, `aria-controls`/`aria-labelledby`, roving `tabindex` (0 on the active tab, -1 on the rest) plus arrow-key/Home/End keyboard navigation. `role="group"` + `aria-pressed` for toggle-button filter groups. `aria-expanded` on any disclosure/hamburger toggle.
- [ ] Prefer native `<details>/<summary>` for genuinely independent expandable sections — it's keyboard-accessible for free. Only use the `name` attribute (exclusive-open accordion groups) when sections are truly mutually exclusive by intent; `tdd.html`'s Deep Dives are deliberately left independent since a reader may want two sections open for comparison.
- [ ] Text is never justified (ties to the WCAG 1.4.8 line-length rule above).

## Content principles

- **Show known gaps and risks, don't sanitize them.** "Here's what I haven't solved yet" reads as more credible than a page that implies everything's finished. Cross-link every gap to its actual GitHub issue — but only after confirming the issue number via `gh issue view`, never guess/hardcode one.
- **Synthetic example data must be visibly flagged as synthetic** (a tag/badge, not just a caption) — especially in a health-data context, never let a walkthrough example read as if it could be real captured patient output.
- `docs/notes/DESIGN.md` and this file follow different update rules: `DESIGN.md` is a point-in-time snapshot re-written only on genuine architectural shifts (see `CLAUDE.md`); this style guide is a living reference — update it whenever a new durable pattern is introduced, same discipline as adding a DEC entry.
