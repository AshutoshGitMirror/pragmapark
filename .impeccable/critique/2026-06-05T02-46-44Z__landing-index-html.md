---
target: landing/index.html
total_score: 29
p0_count: 0
p1_count: 2
timestamp: 2026-06-05T02-46-44Z
slug: landing-index-html
---
# Design Critique: landing/index.html

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Real-time simulation updates are clear. Hover scaling is added. Minor gap: no indication of active/paused state. |
| 2 | Match System / Real World | 3 | Dynamic parking concepts are clear, but terminology leans heavily into developer jargon (MARL, Oracle, Nonce, SHA-256). |
| 3 | User Control and Freedom | 2 | Timeline widgets can be selected, but concurrent autoplaying loops hijack selection and override user focus in 1.2–2.2s. |
| 4 | Consistency and Standards | 3 | Timeline scrubbers now consistently support keyboard focus and standard action listeners, though layout orientations alternate. |
| 5 | Error Prevention | 4 | Read-only simulation page successfully prevents input errors. Keyboard interaction prevents focus traps. |
| 6 | Recognition Rather Than Recall | 3 | Hover scale changes on the custom cursor ring indicate interactive elements, but the native pointer cursor still overlaps on hover. |
| 7 | Flexibility and Efficiency | 3 | Keyboard navigation (tabindex, keydown) is now supported across all timelines, but lacks speed controls or keyboard shortcuts. |
| 8 | Aesthetic and Minimalist Design | 2 | Corrected body text contrast (--muted to #9a97b0). However, --dim (#5c597c) text is 3.03:1 (failing AA). Micro-fonts (7px/8px) persist. |
| 9 | Error Recovery | 3 | N/A (no input errors). |
| 10 | Help and Documentation | 3 | Interactive timelines have narrative text explaining the simulated smart parking behaviors. |
| **Total** | | **29/40** | **Good** |

## Anti-Patterns Verdict

**LLM Assessment**: The page's design is highly technical and immersive, which fits the futuristic hybrid smart parking theme. The recent updates have significantly improved readability and accessibility (focus indicators, prefers-reduced-motion block, and timeline keyboard support). However, some "AI slop" tells remain: typographic indecision persists with three distinct font families (`Syne`, `Fraunces`, and `DM Mono`) forced together in the hero. The double cursor (native pointer overlaying custom ring) and layout-animating dimensions (`width`/`height` on cursor, `height` on cancellation bars) indicate technical shortcuts.

**Deterministic Scan**: The automated detector found 5 warnings and advisories:
- **1 Side-Tab Accent Border**: False positive at line 601 (`border-left` on `.chain-connector::after` draws a CSS triangle arrowhead, not a card border).
- **2 Layout Property Animations**: CSS transitions on `width`/`height` for the custom cursor (line 57) and `height` for `.cancel-bar-inner` (line 563) cause layout thrashing.
- **1 Em-Dash Overuse**: 5 em-dashes found in narrative text strings.
- **1 Numbered Section Marker Sequence**: Eyebrows (01, 02, 03, 04, 05, 10) represent standard AI scaffolding.

## Overall Impression
The Pragma landing page has improved significantly, moving from a poor 18/40 to a solid 29/40. The inclusion of focus-visible styles, prefers-reduced-motion support, keyboard navigable timeline widgets, and improved base text contrast has established a much healthier baseline. The remaining issues are focused on resolving layout-thrashing animations, fixing low-contrast `--dim` text/micro-typography, resolving the double-cursor glitch, and giving the user control to pause/play the autoplaying timelines.

## What's Working
1. **Interactive Timeline Widgets**: Standardizing `tabindex="0"`, `role="button"`, and Enter/Space event handlers makes the timelines fully keyboard-navigable and accessible.
2. **Text Contrast Baseline**: Elevating `--muted` to `#9a97b0` provides a compliant 7.07:1 contrast ratio against the deep `#04040a` canvas.
3. **Motion Adaptability**: The global `@media (prefers-reduced-motion: reduce)` block successfully overrides transitions and keyframe animations for users sensitive to motion.

## Priority Issues

### [P1] Double Cursor Glitch (Jarring UI Overlay)
- **Why it matters**: Hiding the body cursor with `cursor: none` but leaving the default browser pointer cursor on interactive elements (e.g., `.rush-item`, `.bhr`, `.nav-pill`, `.chain-block`, `.cancel-step-btn`, `.marl-tick`) causes the native cursor to reappear and overlap with the custom cursor ring on hover. This ruins the premium aesthetic and looks buggy.
- **Fix**: Apply `cursor: none !important` to all interactive elements under the `@media (hover: hover) and (pointer: fine)` query so that the custom cursor is the *only* cursor visible.
- **Suggested command**: `/impeccable polish`

### [P1] Layout Thrashing (Custom Cursor & Cancellation Bars)
- **Why it matters**: The custom cursor `#cursor` has a CSS transition on `width` and `height`, and the cancellation bars `.cancel-bar-inner` have a CSS transition on `height`. Triggering transitions on layout-impacting dimensions forces the browser to perform layout reflows and repaints constantly on mouse move and step transitions, degrading performance.
- **Fix**: Refactor `#cursor` to use `transform: scale()` for hover scaling and `.cancel-bar-inner` to use `transform: scaleY()` with `transform-origin: bottom` to animate height.
- **Suggested command**: `/impeccable optimize`

### [P2] Text Contrast & Readability Violations (Low-Contrast `--dim` and Micro-typography)
- **Why it matters**: The color `--dim` (`#5c597c`) against the dark background `#04040a` yields a contrast ratio of only 3.03:1, violating the WCAG AA minimum of 4.5:1 for body copy and section headers (e.g., `.section-number`). Furthermore, several UI labels (such as `.rush-occ-label`, `.rush-meta-item .k`, and `.chain-block-prev`) use extremely small font sizes between 7px and 9px, making the text illegible for low-vision users.
- **Fix**: Adjust `--dim` to a lighter hue (e.g., `#7d7a9c` or `#8c89ad` to achieve >= 4.5:1 contrast) and enforce a minimum font size of 12px for all readable text labels.
- **Suggested command**: `/impeccable layout`

### [P2] Autoplay Hijacks Selection & Focus (Uncontrolled Movement)
- **Why it matters**: The 5 timeline sections loop through steps automatically using `setInterval`. When a user manually clicks or tabs to a step to inspect it, the auto-play timer overrides their selection in under 2 seconds. This violates "User Control and Freedom" and ruins the keyboard/screen-reader experience.
- **Fix**: Add a global Play/Pause toggle button to freeze all simulations, or pause auto-play automatically when the element has keyboard focus or user-interaction.
- **Suggested command**: `/impeccable quieter`

### [P2] Typography Over-Indecision
- **Why it matters**: The hero section loads and displays three distinct display font families (`Fraunces` serif, `Syne` geometric, and `DM Mono` monospace) in close proximity. This creates high cognitive load and typographic competition rather than a unified brand system.
- **Fix**: Restrict display text to two font families max (e.g., using `Fraunces` or `Syne` for display, `Syne` for body, and `DM Mono` strictly for numeric/metadata callouts).
- **Suggested command**: `/impeccable typeset`

## Persona Red Flags

### Jordan (Confused First-Timer)
- **Red Flag**: Jordan tries to read the narrative story for Step 4 of the Rush Hour simulation. Because the simulation autoplays every 1.2 seconds, the story text suddenly updates to Step 5 before Jordan can finish reading, forcing them to repeatedly click back.

### Sam (Accessibility-Dependent)
- **Red Flag**: Sam tabs through the page. Although the `:focus-visible` outline is highly visible, the section numbers (e.g. `01 / RUSH HOUR`) and block hashes use `--dim` (#5c597c), which does not have enough contrast (3.03:1) for Sam to read.

### Casey (Distracted Mobile User)
- **Red Flag**: On Casey's phone, the concurrent autoplaying intervals run continuously in the background, consuming CPU resources, causing the device to heat up and draining battery life.

## Minor Observations
- The scroll-hint animation continues to bounce even after the user has scrolled down the page, which adds unnecessary visual noise.
- The horizontal scrollbar for the blockchain section is standard browser styling, which stands out against the dark custom theme.
