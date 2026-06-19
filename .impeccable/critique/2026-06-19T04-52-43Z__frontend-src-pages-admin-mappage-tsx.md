---
target: frontend/src/pages/admin/MapPage.tsx
total_score: 23
p0_count: 0
p1_count: 3
timestamp: 2026-06-19T04-52-43Z
slug: frontend-src-pages-admin-mappage-tsx
---
# Design Critique: Pragma Map Page
**Target:** `frontend/src/pages/admin/MapPage.tsx`

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Selected lot is highlighted on map and panel, but interaction has minor feedback gaps. |
| 2 | Match System / Real World | 3 | Locations and terms match physical coordinates and smart parking domain accurately. |
| 3 | User Control and Freedom | 3 | Can close panels and filter cities, but no simple lot list navigation exists. |
| 4 | Consistency and Standards | 1 | Leaflet popups have default white containers clashing with dark mode. Zoom buttons are bright white. Arbitrary metric coloring. |
| 5 | Error Prevention | 3 | City filtering restricts queries safely, but marker positioning logic lacks guardrails. |
| 6 | Recognition Rather Than Recall | 2 | Map markers lack a color legend. Sidebar prediction legend has no representation on the progress bar. |
| 7 | Flexibility and Efficiency | 2 | No keyboard navigation, list view, or search. Must click markers one-by-one to explore. |
| 8 | Aesthetic and Minimalist Design | 2 | Layout is clean but cluttered by microscopic labels (8px), arbitrary colors, and white Leaflet popup containers. |
| 9 | Error Recovery | 3 | Simple, clean UI for network errors with retry capabilities. |
| 10 | Help and Documentation | 1 | No explanation of dynamic pricing rules or RL/ML prediction inputs. |
| **Total** | | **23/40** | **Acceptable** |

## Anti-Patterns Verdict

**LLM Assessment**: The page has a solid layout structure but exhibits high "AI slop" indicators due to:
1. **The default white Leaflet theme leaking**: The Leaflet popup wrapper (`.leaflet-popup-content-wrapper` and `.leaflet-popup-tip`) and standard zoom buttons are left white, which breaks the dark theme aesthetic.
2. **Numbered section eyebrow**: The text `01 / IOT · OBSERVE` is typical AI boilerplate scaffolding.
3. **Arbitrary colored metrics**: Text colors for numbers are colored green, gold, and cyan without a clear semantic system.
4. **Visual noise / tiny fonts**: Text sizes are as small as `8px` with extremely low color contrast against dark backgrounds.

**Deterministic Scan**: 0 findings from `detect.mjs`.

## Overall Impression
Pragma's Map Page presents a well-structured spatial layout that fits the technical, high-fidelity nature of the project. However, it feels unfinished. The white Leaflet containers, microscopic labels, and arbitrary color schemes destroy the premium "mission control" feeling that the product target calls for. The single biggest opportunity is styling Leaflet components to blend into the dark aesthetic and cleaning up typographic hierarchy.

## What's Working
- **Premium dark map theme**: The CartoDB Dark tile layer coordinates beautifully with the void/dark palette of the dashboard.
- **Marker sizing feedback**: Marker nodes resize when selected to provide instant spatial feedback.
- **Clean panel transition**: The slide-out layout structure for `selectedLot` is clean and keeps the primary view organized.

## Priority Issues
- **[P1] Leaflet Popup Styling Breakdown**:
  - **Why it matters**: The default white popup balloon container wrapping the custom dark inner container looks broken.
  - **Fix**: Override Leaflet CSS styles globally in `index.css` or `MapPage.tsx` to set the popup container background to `#0e0e1c`, add thin borders, and style the arrow tip.
  - **Suggested command**: `/impeccable polish`
- **[P1] Default Leaflet Zoom & Attribution Clash**:
  - **Why it matters**: The white zoom control buttons and bottom-right attribution panel stand out as bright white rectangles in a dark mode application.
  - **Fix**: Apply CSS styles to `.leaflet-bar a` and `.leaflet-control-attribution` to use dark backgrounds, light borders, and muted gray text.
  - **Suggested command**: `/impeccable polish`
- **[P1] Microscopic and Low-Contrast Labels**:
  - **Why it matters**: Spacing and details labels use `text-[8px]` and `text-[9px]` in `#5a6a8a` which is unreadable. The color contrast ratio is ~2.5:1, failing the WCAG AA requirement of 4.5:1.
  - **Fix**: Set the minimum font size for labels to `11px` (or `0.7rem`) and bump the color to `#94a3b8` or `#e2e8f0`.
  - **Suggested command**: `/impeccable typeset`
- **[P2] Arbitrary Metric Color Coding**:
  - **Why it matters**: Colors like teal, gold, and green are assigned to metrics arbitrarily, which confuses users who expect color to convey severity or status.
  - **Fix**: Use white/off-white for standard numbers and reserve color tags strictly for semantic conditions (e.g. red for occupancy >75%).
  - **Suggested command**: `/impeccable colorize`
- **[P2] Misleading 'Predicted' Indicator**:
  - **Why it matters**: The legend `▬ predicted` is displayed on the sidebar but has no representation on the occupancy progress bar itself.
  - **Fix**: Blend a secondary dashed or semi-transparent layer on the progress bar to visualize the predicted value.
  - **Suggested command**: `/impeccable layout`

## Persona Red Flags
- **Alex (Impatient Power User)**:
  - **Red Flag**: Alex has no search bar or lot list view to immediately select or query a lot. Finding a lot requires manual navigation and clicking on the map markers.
- **Sam (Accessibility-Dependent)**:
  - **Red Flag**: Sam cannot use this page due to microscopic `8px`/`9px` fonts and low contrast text (2.5:1). Additionally, the custom `divIcon` markers are not keyboard focusable and lack ARIA status tags.
- **Jordan (Confused First-Timer)**:
  - **Red Flag**: The map markers use three colors (rose, gold, cyan) to represent different occupancy levels, but there is no map legend. Jordan has to guess what a cyan marker means.

## Minor Observations
- The "✕" close button in the details panel is too small and lacks hover feedback.
- Large serif font is used in the popup header, but the layout is otherwise clean, sans-serif or monospaced. It creates a slight font mismatch.

## Questions to Consider
- What if the Map Page had a collapsible list view on the left, allowing users to search and sort lots by occupancy or name?
- Can we introduce a clear, interactive color legend at the bottom of the map for the marker pins?
